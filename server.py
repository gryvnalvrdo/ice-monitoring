import os
import io
import csv
import glob
import time
import asyncio
import threading
import logging
from datetime import datetime
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import database
from security import (
    security_manager,
    verify_api_key,
    SESSION_COOKIE_NAME,
    ALLOWED_VIDEO_EXTS,
    is_auth_configured,
    authenticate_user,
    login_rate_limiter,
    session_manager,
    get_session_from_cookies,
    require_session,
    verify_csrf,
    require_admin_csrf,
    mask_rtsp_url,
    validate_video_source,
    resolve_safe_file,
    sanitize_csv_cell,
)
from hardware import hardware
from stream_manager import RTSPStreamManager
from cloud_sync import cloud_sync
from engine import IceDetectionEngine
from power_watchdog import power_watchdog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.init_db()
    os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)
    if cloud_sync.is_enabled:
        cloud_sync.start()
    power_watchdog.check_recovery_on_boot(cloud_sync_mgr=cloud_sync)
    power_watchdog.start_heartbeat()
    logger.info("Server FastAPI siap di port 8000.")
    yield
    global is_engine_active
    is_engine_active = False
    power_watchdog.stop_heartbeat(clean_shutdown=True)
    cloud_sync.stop()
    if global_engine is not None:
        engine = global_engine
        try:
            database.log_anomaly(
                session_id=engine.current_session_id,
                frame_idx=engine.frame_idx,
                anomaly_type="SYSTEM_SHUTDOWN",
                status="CONFIRMED_THEFT",
                details=f"Server aplikasi dimatikan. Total es terakhir: {engine.detector.total}"
            )
            engine.telegram.send_alert(
                title="SERVER MONITORING DIMATIKAN",
                details={
                    'city': config.DEFAULT_CITY,
                    'truck_id': engine.current_truck_id or "-",
                    'trip_number': engine.current_trip_number,
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'message': f"Server aplikasi dimatikan. Total es terakhir: {engine.detector.total} kantong."
                }
            )
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error saat logging shutdown: {e}")
    logger.info("Server FastAPI dihentikan.")

app = FastAPI(
    title="Sistem Monitoring Loading Es Kristal",
    version="2.0",
    lifespan=lifespan,
    docs_url=None if getattr(config, "DISABLE_API_DOCS", True) else "/docs",
    redoc_url=None if getattr(config, "DISABLE_API_DOCS", True) else "/redoc",
    openapi_url=None if getattr(config, "DISABLE_API_DOCS", True) else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key", "X-CSRF-Token"],
)

_engine_lock = threading.Lock()
_create_engine_lock = threading.Lock()
global_engine: Optional[IceDetectionEngine] = None
engine_thread: Optional[threading.Thread] = None
is_engine_active = False

_ws_lock = threading.Lock()
ws_clients_by_sid: dict[str, set[WebSocket]] = defaultdict(set)

_rate_limit_counters: dict = defaultdict(list)
RATE_LIMIT_MAX = 15
RATE_LIMIT_WINDOW = 60.0

def _audit_log(event: str, username: str, ip: str, detail: str = ""):
    try:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        path = os.path.join(config.LOG_DIR, "security_audit.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_detail = mask_rtsp_url(detail).replace("\n", " ").replace("\r", " ")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {event} | user={username} | ip={ip} | {safe_detail}\n")
    except Exception as e:
        logger.error(f"[AUDIT] Gagal tulis log audit: {e}")

def _check_rate_limit(action_key: str = "global") -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    hits = _rate_limit_counters[action_key]
    _rate_limit_counters[action_key] = [t for t in hits if t > window_start]
    if len(_rate_limit_counters[action_key]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_counters[action_key].append(now)
    return True

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def get_or_create_engine() -> IceDetectionEngine:
    global global_engine
    if global_engine is None:
        with _create_engine_lock:
            if global_engine is None:
                global_engine = IceDetectionEngine(
                    video_source=config.VIDEO_SOURCE,
                    city=config.DEFAULT_CITY
                )
    return global_engine

def _classify_anomaly(a: dict) -> str:
    atype = str(a.get("anomaly_type") or "")
    status = str(a.get("status") or "")
    if status == "RECOVERED_TO_TRUCK":
        return "recovered"
    if (
        atype in ("CAMERA_DISCONNECTED", "CAMERA_RECONNECTED", "SYSTEM_SHUTDOWN", "SYSTEM_ENGINE_STOPPED")
        or atype.startswith("CAMERA_TAMPER_")
    ):
        return "camera"
    if status == "CONFIRMED_THEFT":
        return "theft"
    return "pending"

def _decorate_and_count_anomalies(anomalies: list) -> tuple[list, dict]:
    counts = {"theft_count": 0, "camera_issue_count": 0, "recovered_count": 0, "pending_count": 0}
    out = []
    for item in anomalies:
        row = dict(item)
        cat = _classify_anomaly(row)
        row["category"] = cat
        clip = str(row.get("video_clip_path") or "").strip()
        if clip:
            fname = os.path.basename(clip)
            row["video_available"] = bool(fname and os.path.isfile(os.path.join(config.EVIDENCE_DIR, fname)))
        else:
            row["video_available"] = False
        if row.get("details"):
            row["details"] = mask_rtsp_url(row["details"])
        out.append(row)
        if cat == "theft":
            counts["theft_count"] += 1
        elif cat == "camera":
            counts["camera_issue_count"] += 1
        elif cat == "recovered":
            counts["recovered_count"] += 1
        else:
            counts["pending_count"] += 1
    return out, counts

def _sanitized_telemetry(engine: IceDetectionEngine) -> dict:
    t = dict(engine.telemetry)
    t["is_running"] = bool(is_engine_active)
    t["camera_profile"] = getattr(config, "CAMERA_PROFILE", "cam3")
    if "last_event" in t:
        t["last_event"] = mask_rtsp_url(t["last_event"])
    return t

def _make_standby_jpeg(text: str) -> bytes:
    img = np.full((360, 640, 3), 241, dtype=np.uint8)
    cv2.putText(img, text, (95, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (30, 41, 59), 2)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return buf.tobytes() if ok else b""

def _list_safe_sources() -> list[dict]:
    items = []
    cfg_src = getattr(config, "VIDEO_SOURCE", "")
    if cfg_src:
        items.append({
            "value": "preset:configured",
            "label": f"Kamera / Sumber Utama ({mask_rtsp_url(os.path.basename(cfg_src) if not cfg_src.lower().startswith('rtsp') else cfg_src)})",
            "is_rtsp": cfg_src.lower().startswith(("rtsp://", "rtsps://")),
        })
    vdir = os.path.join(BASE_DIR, "videos")
    if os.path.isdir(vdir):
        for fname in sorted(os.listdir(vdir)):
            if os.path.splitext(fname)[1].lower() in ALLOWED_VIDEO_EXTS:
                rel = f"videos/{fname}"
                items.append({
                    "value": rel,
                    "label": f"Rekaman Video: {fname}",
                    "is_rtsp": False,
                })
    return items

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    path = request.url.path
    if path in ("/", "/login") or path.startswith("/api/") or path == "/assets/dashboard.js":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"[SERVER ERROR] {request.method} {request.url.path}: {mask_rtsp_url(str(exc))}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan internal pada server."}
    )

def background_engine_worker(source_path: str, start_minute: float = 0.0, max_frames: int = 0, camera_profile: str = None):
    global is_engine_active
    engine = get_or_create_engine()
    engine.video_source = source_path
    engine.is_running = True
    is_engine_active = True

    cap = None
    stream = None
    hw_stride = hardware.hardware_info.get('recommended_stride', 1)
    is_rtsp = str(source_path).lower().startswith(("rtsp://", "rtsps://"))

    try:
        if camera_profile and hasattr(config, "apply_camera_profile"):
            config.apply_camera_profile(camera_profile)
        try:
            d_init = security_manager.check_and_prune_disk()
            engine._update_telemetry(disk_free_gb=d_init['free_gb'])
        except Exception:
            pass

        if not is_rtsp:
            cap = cv2.VideoCapture(source_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
            start_frame = int(start_minute * 60 * fps)
            if start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            logger.info(f"[WORKER] Menjalankan engine pada file: {mask_rtsp_url(source_path)} (menit {start_minute})")
            engine._update_telemetry(stream_status='CONNECTED')

            f_count = 0
            t0 = time.time()
            disk_check_counter = 0
            telegram_flush_counter = 0

            while is_engine_active and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    logger.info("[WORKER] Akhir video atau stream selesai.")
                    break

                if hw_stride > 1 and f_count % hw_stride != 0:
                    f_count += 1
                    continue

                f_count += 1
                disk_check_counter += 1
                telegram_flush_counter += 1

                engine.process_frame(frame)

                elapsed = time.time() - t0
                engine.fps = f_count / elapsed if elapsed > 0 else fps
                engine.telemetry['fps'] = round(engine.fps, 1)
                engine.telemetry['frame_idx'] = engine.frame_idx

                if disk_check_counter >= 200:
                    disk_check_counter = 0
                    try:
                        d_info = security_manager.check_and_prune_disk()
                        engine._update_telemetry(disk_free_gb=d_info['free_gb'])
                    except Exception as e:
                        logger.error(f"[WORKER] Error disk check: {e}")

                if telegram_flush_counter >= 300:
                    telegram_flush_counter = 0
                    try:
                        engine.telegram.flush_offline_queue()
                    except Exception as e:
                        logger.error(f"[WORKER] Error telegram flush: {e}")

                time.sleep(max(0.01, (1.0 / fps) * 0.3))

                if max_frames > 0 and f_count >= max_frames:
                    break
        else:
            stream = RTSPStreamManager(
                source=source_path,
                fps_target=10.0,
                on_tampering=engine._on_tampering,
                on_disconnect=engine._on_stream_disconnect,
                on_reconnect=engine._on_stream_reconnect
            )
            stream.start()
            engine._update_telemetry(stream_status='CONNECTED')
            logger.info(f"[WORKER] RTSP Stream aktif: {mask_rtsp_url(source_path)}")

            f_count = 0
            t0 = time.time()
            disk_check_counter = 0
            telegram_flush_counter = 0
            last_frame_idx = -1

            while is_engine_active:
                ok, frame, fidx = stream.get_latest_frame()
                if not ok or frame is None:
                    time.sleep(0.04)
                    continue

                if fidx == last_frame_idx:
                    time.sleep(0.02)
                    continue
                last_frame_idx = fidx

                if hw_stride > 1 and f_count % hw_stride != 0:
                    f_count += 1
                    continue

                f_count += 1
                disk_check_counter += 1
                telegram_flush_counter += 1

                engine.process_frame(frame)

                elapsed = time.time() - t0
                engine.fps = f_count / elapsed if elapsed > 0 else 10.0
                engine.telemetry['fps'] = round(engine.fps, 1)
                engine.telemetry['frame_idx'] = engine.frame_idx

                st_state = stream.tamper_status if stream.tamper_status != 'NORMAL' else ('CONNECTED' if stream.is_connected else 'RECONNECTING')
                engine.telemetry['stream_status'] = st_state

                if disk_check_counter >= 200:
                    disk_check_counter = 0
                    try:
                        d_info = security_manager.check_and_prune_disk()
                        engine._update_telemetry(disk_free_gb=d_info['free_gb'])
                    except Exception as e:
                        logger.error(f"[WORKER] Error disk check: {e}")

                if telegram_flush_counter >= 300:
                    telegram_flush_counter = 0
                    try:
                        engine.telegram.flush_offline_queue()
                    except Exception as e:
                        logger.error(f"[WORKER] Error telegram flush: {e}")
    except Exception as e:
        logger.exception(f"[WORKER] Error fatal worker: {mask_rtsp_url(str(e))}")
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
        try:
            engine.close_session()
        except Exception:
            pass
        engine.is_running = False
        is_engine_active = False
        engine._update_telemetry(stream_status='IDLE')
        logger.info("[WORKER] Background worker selesai.")

@app.get("/login")
def login_page(request: Request):
    if get_session_from_cookies(request.cookies, touch=False):
        return RedirectResponse(url="/", status_code=302)
    return FileResponse(os.path.join(WEB_DIR, "login.html"), media_type="text/html")

@app.get("/")
def index_page(request: Request):
    if not get_session_from_cookies(request.cookies, touch=True):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(os.path.join(WEB_DIR, "dashboard.html"), media_type="text/html")

@app.get("/assets/styles.css")
def asset_css():
    return FileResponse(os.path.join(WEB_DIR, "styles.css"), media_type="text/css")

@app.get("/assets/login.js")
def asset_login_js():
    return FileResponse(os.path.join(WEB_DIR, "login.js"), media_type="application/javascript")

@app.get("/assets/dashboard.js")
def asset_dashboard_js(_: dict = Depends(require_session)):
    return FileResponse(os.path.join(WEB_DIR, "dashboard.js"), media_type="application/javascript")

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
def api_login(req: LoginRequest, request: Request):
    ip = _client_ip(request)
    if not is_auth_configured():
        raise HTTPException(status_code=503, detail="Kata sandi login belum dikonfigurasi di .env")

    locked_sec = login_rate_limiter.check_locked(ip)
    if locked_sec > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Terlalu banyak percobaan login salah. Coba lagi dalam {locked_sec} detik."
        )

    user = authenticate_user(req.username, req.password)
    if not user:
        lock = login_rate_limiter.record_failure(ip)
        _audit_log("LOGIN_FAILED", (req.username or "").strip()[:40], ip)
        if lock > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Terlalu banyak percobaan salah. Akun dikunci sementara {lock} detik."
            )
        raise HTTPException(status_code=401, detail="Nama pengguna atau kata sandi salah.")

    login_rate_limiter.reset(ip)
    sess = session_manager.create_session(user["username"], user["role"], ip)
    _audit_log("LOGIN_SUCCESS", user["username"], ip, f"role={user['role']}")

    resp = JSONResponse({
        "username": sess["username"],
        "role": sess["role"],
        "csrf_token": sess["csrf_token"],
    })
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=sess["sid"],
        httponly=True,
        samesite="lax",
        secure=getattr(config, "COOKIE_SECURE", False),
        max_age=int(getattr(config, "SESSION_TTL_MINUTES", 480) * 60),
        path="/",
    )
    return resp

@app.post("/api/auth/logout")
async def api_logout(request: Request):
    ip = _client_ip(request)
    sess = get_session_from_cookies(request.cookies, touch=False)
    if sess:
        verify_csrf(request, sess)
        session_manager.revoke_session(sess["sid"])
        _audit_log("LOGOUT", sess["username"], ip)
        with _ws_lock:
            sockets = list(ws_clients_by_sid.pop(sess["sid"], set()))
        for ws in sockets:
            try:
                await ws.close(code=1008)
            except Exception:
                pass
    resp = JSONResponse({"status": "logged_out"})
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp

@app.get("/api/auth/me")
def api_me(sess: dict = Depends(require_session)):
    return {
        "username": sess["username"],
        "role": sess["role"],
        "csrf_token": sess["csrf_token"],
        "allow_simulation": bool(getattr(config, "ALLOW_SIMULATION", False)),
    }

@app.get("/api/overview")
def get_overview(city: str = config.DEFAULT_CITY, date: Optional[str] = None, _: dict = Depends(require_session)):
    summary = database.get_daily_summary(city=city, target_date=date)
    decorated_anoms, stats = _decorate_and_count_anomalies(summary.get("anomalies", []))
    engine = get_or_create_engine()
    src = engine.video_source or ""
    src_is_rtsp = src.lower().startswith(("rtsp://", "rtsps://"))
    src_label = mask_rtsp_url(src) if src_is_rtsp else (os.path.basename(src) if src else "Standby")

    try:
        storage_info = security_manager.check_and_prune_disk()
    except Exception:
        storage_info = {"free_gb": 0, "used_percent": 0}

    return {
        "city": city,
        "summary": {
            "total_trucks": summary.get("total_trucks", 0),
            "total_trips": summary.get("total_trips", 0),
            "total_large": summary.get("total_large", 0),
            "total_small": summary.get("total_small", 0),
            "grand_total": summary.get("grand_total", 0),
            "date": summary.get("date"),
        },
        "stats": stats,
        "trips": summary.get("trips", []),
        "anomalies": decorated_anoms,
        "live_telemetry": _sanitized_telemetry(engine),
        "is_active": is_engine_active,
        "active_source_label": src_label,
        "source_is_rtsp": src_is_rtsp,
        "available_cameras": list(config.CAMERA_PROFILES.keys()),
        "allow_simulation": bool(getattr(config, "ALLOW_SIMULATION", False)),
        "storage": storage_info,
        "cloud": {
            "is_enabled": cloud_sync.is_enabled,
            "sync_status": cloud_sync.sync_status,
            "last_sync_time": cloud_sync.last_sync_time,
        },
    }

@app.get("/api/cameras")
def api_cameras(_: dict = Depends(require_session)):
    return {
        "active_profile": getattr(config, "CAMERA_PROFILE", "cam3"),
        "profiles": [
            {"id": "cam3", "label": "Kamera 3 — Papan Loading Utama"},
            {"id": "cam10", "label": "Kamera 10 — Area Samping Papan"},
        ],
        "sources": _list_safe_sources(),
    }

class CameraSelectRequest(BaseModel):
    camera_profile: str

@app.post("/api/camera/select")
def api_select_camera(req: CameraSelectRequest, request: Request, sess: dict = Depends(require_admin_csrf)):
    key = (req.camera_profile or "").strip().lower()
    if key not in config.CAMERA_PROFILES:
        raise HTTPException(status_code=400, detail="Profil kamera tidak dikenal.")
    with _engine_lock:
        if is_engine_active:
            raise HTTPException(status_code=409, detail="Hentikan pemantauan terlebih dahulu sebelum mengganti profil kamera.")
        config.apply_camera_profile(key)
        engine = get_or_create_engine()
        engine._update_telemetry(camera_profile=key)
    _audit_log("CAMERA_SELECT", sess["username"], _client_ip(request), f"profile={key}")
    return {"status": "ok", "camera_profile": key}

@app.get("/api/trips")
def list_trips(city: Optional[str] = None, date: Optional[str] = None, truck_id: Optional[str] = None, _: dict = Depends(require_session)):
    return database.get_all_sessions(city=city, target_date=date, truck_id=truck_id)

@app.get("/api/trips/{trip_id}")
def get_trip_detail(trip_id: int, _: dict = Depends(require_session)):
    detail = database.get_session_detail(trip_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    detail["anomalies"], _ = _decorate_and_count_anomalies(detail.get("anomalies", []))
    return detail

@app.get("/api/anomalies")
def list_anomalies(limit: int = 50, _: dict = Depends(require_session)):
    limit = max(1, min(limit, 500))
    rows, _ = _decorate_and_count_anomalies(database.get_anomalies(limit=limit))
    return rows

@app.get("/api/reports/export")
def export_csv_report(date: Optional[str] = None, city: str = config.DEFAULT_CITY, _: dict = Depends(require_session)):
    target_date = date or time.strftime("%Y-%m-%d")
    trips = database.get_all_sessions(city=city, target_date=target_date)

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["Tanggal", "Jam Mulai", "Jam Selesai", "Nomor Truk", "Trip Ke", "Es Besar", "Es Kecil", "Total Kantong", "Durasi (Detik)", "Status"])
    for tr in trips:
        writer.writerow([
            sanitize_csv_cell(target_date),
            sanitize_csv_cell(tr.get("start_time", "")),
            sanitize_csv_cell(tr.get("end_time", "")),
            sanitize_csv_cell(tr.get("truck_id", "")),
            sanitize_csv_cell(tr.get("trip_number", 1)),
            sanitize_csv_cell(tr.get("count_large", 0)),
            sanitize_csv_cell(tr.get("count_small", 0)),
            sanitize_csv_cell(tr.get("count_total", 0)),
            sanitize_csv_cell(tr.get("duration_sec", 0)),
            sanitize_csv_cell("Selesai" if tr.get("status") == "completed" else "Sedang Muat"),
        ])

    safe_date = "".join(c for c in target_date if c.isalnum() or c == "-") or "laporan"
    headers = {"Content-Disposition": f'attachment; filename="laporan_muat_es_{safe_date}.csv"'}
    return StreamingResponse(iter([buf.getvalue().encode("utf-8")]), media_type="text/csv; charset=utf-8", headers=headers)

@app.get("/api/evidence/{filename}")
def get_evidence_video(filename: str, _: dict = Depends(require_session)):
    path = resolve_safe_file(config.EVIDENCE_DIR, filename, (".mp4", ".avi"))
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File video bukti tidak ditemukan")
    return FileResponse(path, media_type="video/mp4")

@app.get("/api/snapshots/{filename}")
def get_snapshot_image(filename: str, _: dict = Depends(require_session)):
    path = resolve_safe_file(config.SNAPSHOT_DIR, filename, (".jpg", ".jpeg", ".png"))
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Foto hitungan tidak ditemukan")
    return FileResponse(path, media_type="image/jpeg")

@app.get("/api/stream/live")
async def stream_live_mjpeg(request: Request, sess: dict = Depends(require_session)):
    sid = sess["sid"]
    engine = get_or_create_engine()
    warmup_jpg = _make_standby_jpeg("Menghubungkan kamera...")

    async def frame_generator():
        ticks = 0
        while True:
            if await request.is_disconnected():
                break
            if ticks % 15 == 0 and not session_manager.get_session(sid, touch=False):
                break
            if not is_engine_active:
                break
            jpg = engine.get_latest_jpeg() or warmup_jpg
            if jpg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                )
            ticks += 1
            await asyncio.sleep(0.12)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/engine/status")
def get_engine_status(_: dict = Depends(require_session)):
    engine = get_or_create_engine()
    return {
        "is_active": is_engine_active,
        "telemetry": _sanitized_telemetry(engine),
    }

@app.get("/api/hardware/status")
def get_hardware_status(_: dict = Depends(require_session)):
    return hardware.get_summary()

@app.get("/api/storage/status")
def get_storage_status(_: dict = Depends(require_session)):
    return security_manager.check_and_prune_disk()

@app.get("/api/cloud/status")
def get_cloud_status(_: dict = Depends(require_session)):
    return {
        "is_enabled": cloud_sync.is_enabled,
        "sync_status": cloud_sync.sync_status,
        "last_sync_time": cloud_sync.last_sync_time,
        "synced_state": cloud_sync.state,
    }

@app.post("/api/cloud/sync")
def trigger_cloud_sync(sess: dict = Depends(require_admin_csrf)):
    return cloud_sync.sync_now()

class StartEngineRequest(BaseModel):
    source: str = "preset:configured"
    start_minute: float = 0.0
    max_frames: int = 0
    camera_profile: Optional[str] = None

@app.post("/api/engine/start")
def start_engine(req: StartEngineRequest, request: Request, sess: dict = Depends(require_admin_csrf)):
    global is_engine_active, engine_thread

    if not _check_rate_limit("engine_start"):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan. Coba lagi nanti.")

    raw_src = config.VIDEO_SOURCE if req.source == "preset:configured" else req.source
    try:
        validated_src = validate_video_source(raw_src)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    if not (0.0 <= req.start_minute <= 300.0):
        raise HTTPException(status_code=400, detail="Menit mulai harus berada di rentang 0 sampai 300 menit.")

    cam_profile = (req.camera_profile or getattr(config, "CAMERA_PROFILE", "cam3")).lower()
    if cam_profile not in config.CAMERA_PROFILES:
        raise HTTPException(status_code=400, detail="Profil kamera tidak dikenal.")

    with _engine_lock:
        if is_engine_active:
            return {"status": "already_running", "message": "Pemantauan sudah berjalan."}
        is_engine_active = True
        engine_thread = threading.Thread(
            target=background_engine_worker,
            args=(validated_src, req.start_minute, req.max_frames, cam_profile),
            daemon=True,
        )
        engine_thread.start()

    masked = mask_rtsp_url(validated_src)
    _audit_log("ENGINE_START", sess["username"], _client_ip(request), f"src={masked} cam={cam_profile}")
    return {"status": "started", "source": masked, "start_minute": req.start_minute, "camera_profile": cam_profile}

@app.post("/api/engine/stop")
def stop_engine(request: Request, sess: dict = Depends(require_admin_csrf)):
    global is_engine_active
    engine = get_or_create_engine()

    with _engine_lock:
        was_active = is_engine_active
        is_engine_active = False

    if was_active:
        _audit_log("ENGINE_STOP", sess["username"], _client_ip(request), f"total={engine.detector.total}")
        try:
            database.log_anomaly(
                session_id=engine.current_session_id,
                frame_idx=engine.frame_idx,
                anomaly_type="SYSTEM_ENGINE_STOPPED",
                status="CONFIRMED_THEFT",
                details=f"Pemantauan dihentikan oleh {sess['username']}. Total es saat ini: {engine.detector.total} (B:{engine.detector.total_large}, K:{engine.detector.total_small})"
            )
            engine.telegram.send_alert_async(
                title="DETEKSI MONITORING DIHENTIKAN",
                details={
                    "city": config.DEFAULT_CITY,
                    "truck_id": engine.current_truck_id or "-",
                    "trip_number": engine.current_trip_number,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "message": f"Deteksi dihentikan oleh {sess['username']} via dashboard. Total es: {engine.detector.total} kantong.",
                },
            )
        except Exception as e:
            logger.error(f"[STOP] Gagal mencatat event stop: {e}")

    return {"status": "stopped", "message": "Perintah berhenti dikirim dan dicatat."}

@app.post("/api/engine/simulate_incident")
def simulate_incident(incident_type: str = "recovered", sess: dict = Depends(require_admin_csrf)):
    if not getattr(config, "ALLOW_SIMULATION", False):
        raise HTTPException(status_code=403, detail="Mode simulasi dinonaktifkan di lingkungan produksi.")
    if not _check_rate_limit("simulate"):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan simulasi. Coba lagi nanti.")

    engine = get_or_create_engine()
    if incident_type == "recovered":
        anom_id = database.log_anomaly(
            session_id=engine.current_session_id,
            frame_idx=engine.frame_idx,
            anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
            status="PENDING",
            details="[SIMULASI] Es tergeser ke samping kiri papan",
        )
        time.sleep(0.3)
        database.update_anomaly(
            anomaly_id=anom_id,
            status="RECOVERED_TO_TRUCK",
            details="[SIMULASI] Pekerja mengembalikan es ke dalam truk. Alarm dibatalkan!",
        )
        engine._update_telemetry(last_event="Simulasi: Es samping kembali masuk bak (False Alarm dicegah)")
        return {"status": "success", "type": "recovered", "message": "Es kembali ke truk. Alarm dibatalkan."}

    database.log_anomaly(
        session_id=engine.current_session_id,
        frame_idx=engine.frame_idx,
        anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
        status="CONFIRMED_THEFT",
        details="[SIMULASI] Es keluar ke samping kanan dan tidak masuk truk!",
    )
    engine._update_telemetry(
        active_anomalies_count=engine.telemetry["active_anomalies_count"] + 1,
        last_event="Simulasi: Dugaan pencurian es ke samping terkonfirmasi!",
    )
    engine.telegram.send_alert_async(
        title="DUGAAN PENCURIAN ES TERDETEKSI (SIMULASI)",
        details={
            "city": config.DEFAULT_CITY,
            "truck_id": engine.current_truck_id or "18",
            "trip_number": engine.current_trip_number,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Simulasi pencurian: es keluar ke samping dan tidak masuk truk.",
        },
    )
    return {"status": "success", "type": "theft", "message": "Simulasi pencurian dicatat."}

@app.post("/api/engine/simulate_power_outage")
def api_simulate_power_outage(downtime_minutes: int = 15, sess: dict = Depends(require_admin_csrf)):
    if not getattr(config, "ALLOW_SIMULATION", False):
        raise HTTPException(status_code=403, detail="Mode simulasi dinonaktifkan di lingkungan produksi.")
    if not _check_rate_limit("simulate"):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan simulasi. Coba lagi nanti.")

    res = power_watchdog.simulate_power_outage(downtime_minutes=downtime_minutes, cloud_sync_mgr=cloud_sync)
    engine = get_or_create_engine()
    engine._update_telemetry(last_event=f"Listrik mati ({res['downtime']}) pulih kembali!")
    return res

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    sess = get_session_from_cookies(websocket.cookies, touch=True)
    if not sess:
        await websocket.close(code=4401)
        return

    sid = sess["sid"]
    await websocket.accept()
    with _ws_lock:
        ws_clients_by_sid[sid].add(websocket)

    engine = get_or_create_engine()
    try:
        while True:
            if not session_manager.get_session(sid, touch=False):
                await websocket.close(code=1008)
                break
            await websocket.send_json(_sanitized_telemetry(engine))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        with _ws_lock:
            ws_clients_by_sid[sid].discard(websocket)
            if not ws_clients_by_sid[sid]:
                ws_clients_by_sid.pop(sid, None)

if __name__ == "__main__":
    import uvicorn
    logger.info("Menjalankan Web Server & AI Engine di http://localhost:8000 ...")
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
