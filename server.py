import os
import time
import asyncio
import threading
import logging
import pathlib
from collections import defaultdict
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import database
from security import security_manager, verify_api_key
from hardware import hardware
from stream_manager import RTSPStreamManager
from cloud_sync import cloud_sync
from engine import IceDetectionEngine
from power_watchdog import power_watchdog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

app = FastAPI(title="Sistem Monitoring Loading Es Kristal", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engine singleton & worker thread
global_engine: Optional[IceDetectionEngine] = None
engine_thread: Optional[threading.Thread] = None
is_engine_active = False

# Active WebSocket connections
ws_clients = set()

# In-Memory Rate Limiter (IP / Action based)
_rate_limit_counters: dict = defaultdict(list)
RATE_LIMIT_MAX = 15       # Max 15 requests
RATE_LIMIT_WINDOW = 60.0  # per 60 seconds

def _check_rate_limit(action_key: str = "global") -> bool:
    """
    return html.replace("__CITY__", city_label).replace("__BRANCH__", branch_code)Mengembalikan True jika request diizinkan, False jika terkena rate-limit."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    hits = _rate_limit_counters[action_key]
    _rate_limit_counters[action_key] = [t for t in hits if t > window_start]
    if len(_rate_limit_counters[action_key]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_counters[action_key].append(now)
    return True


def get_or_create_engine() -> IceDetectionEngine:
    global global_engine
    if global_engine is None:
        global_engine = IceDetectionEngine(
            video_source=config.VIDEO_SOURCE,
            city=config.DEFAULT_CITY
        )
    return global_engine


def background_engine_worker(source_path: str, start_minute: float = 28.5, max_frames: int = 0):
    global is_engine_active, global_engine
    import cv2

    engine = get_or_create_engine()
    engine.video_source = source_path
    engine.is_running = True
    is_engine_active = True

    hw_stride = hardware.hardware_info.get('recommended_stride', 1)
    is_rtsp = str(source_path).lower().startswith("rtsp://") or str(source_path).lower().startswith("http://")

    # Ambil status disk awal
    try:
        d_init = security_manager.check_and_prune_disk()
        engine._update_telemetry(disk_free_gb=d_init['free_gb'])
    except Exception:
        pass

    if not is_rtsp:
        # MODE 1: FILE VIDEO OFFLINE / REKAMAN TESTING (cv2 seek)
        cap = cv2.VideoCapture(source_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
        start_frame = int(start_minute * 60 * fps)
        if start_frame > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        logger.info(f"[WORKER] Menjalankan engine pada file: {source_path} (mulai frame {start_frame}, menit {start_minute})")
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

            # CPU mode stride check
            if hw_stride > 1 and f_count % hw_stride != 0:
                f_count += 1
                continue

            f_count += 1
            disk_check_counter += 1
            telegram_flush_counter += 1

            processed_frame, events = engine.process_frame(frame)

            # Hitung realtime FPS
            elapsed = time.time() - t0
            engine.fps = f_count / elapsed if elapsed > 0 else fps
            engine.telemetry['fps'] = round(engine.fps, 1)
            engine.telemetry['frame_idx'] = engine.frame_idx

            # Auto disk prune setiap 200 frame
            if disk_check_counter >= 200:
                disk_check_counter = 0
                try:
                    d_info = security_manager.check_and_prune_disk()
                    engine._update_telemetry(disk_free_gb=d_info['free_gb'])
                except Exception as e:
                    logger.error(f"[WORKER] Error disk check: {e}")

            # Flush offline queue telegram setiap 300 frame
            if telegram_flush_counter >= 300:
                telegram_flush_counter = 0
                try:
                    engine.telegram.flush_offline_queue()
                except Exception as e:
                    logger.error(f"[WORKER] Error telegram flush: {e}")

            # Throttle ringan agar menyerupai kecepatan CCTV asli
            time.sleep(max(0.01, (1.0 / fps) * 0.3))

            if max_frames > 0 and f_count >= max_frames:
                break

        cap.release()

    else:
        # MODE 2: LIVE RTSP / CCTV REAL-TIME STREAM (RTSPStreamManager Resilient)
        stream = RTSPStreamManager(
            source=source_path,
            fps_target=10.0,
            on_tampering=engine._on_tampering,
            on_disconnect=engine._on_stream_disconnect,
            on_reconnect=engine._on_stream_reconnect
        )
        stream.start()
        engine._update_telemetry(stream_status='CONNECTED')
        logger.info(f"[WORKER] RTSP Stream aktif: {source_path}")

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

            processed_frame, events = engine.process_frame(frame)

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

        stream.stop()

    engine.close_session()
    engine.is_running = False
    is_engine_active = False
    engine._update_telemetry(stream_status='IDLE')
    logger.info("[WORKER] Background worker selesai.")


# ===================== REST API ENDPOINTS =====================

@app.on_event("startup")
def on_startup():
    database.init_db()
    os.makedirs(config.EVIDENCE_DIR, exist_ok=True)
    if cloud_sync.is_enabled:
        cloud_sync.start()

    # Periksa pemulihan mati listrik mendadak & aktifkan heartbeat
    power_watchdog.check_recovery_on_boot(cloud_sync_mgr=cloud_sync)
    power_watchdog.start_heartbeat()

    logger.info("Server FastAPI siap di port 8000.")


@app.on_event("shutdown")
def on_shutdown():
    power_watchdog.stop_heartbeat(clean_shutdown=True)
    cloud_sync.stop()
    engine = get_or_create_engine()
    if engine:
        try:
            database.log_anomaly(
                session_id=engine.current_session_id or 1,
                frame_idx=engine.frame_idx,
                anomaly_type="SYSTEM_SHUTDOWN",
                status="CONFIRMED_THEFT",
                details=f"Server aplikasi dimatikan / proses Python dihentikan. Total es terakhir: {engine.detector.total}"
            )
            engine.telegram.send_alert(
                title="SERVER MONITORING DIMATIKAN",
                details={
                    'city': config.DEFAULT_CITY,
                    'truck_id': engine.current_truck_id or "-",
                    'trip_number': engine.current_trip_number,
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'message': f"Server aplikasi dimatikan / komputer di-shutdown. Total es terakhir: {engine.detector.total} kantong."
                }
            )
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error saat logging shutdown: {e}")
    logger.info("Server FastAPI dihentikan.")


@app.get("/api/overview")
def get_overview(city: str = config.DEFAULT_CITY, date: Optional[str] = None):
    """
    Ringkasan dashboard hari ini untuk kota tertentu:
    - Total truk berangkat
    - Total trip
    - Total es besar & kecil
    - List trip hari ini
    - List anomali
    """
    summary = database.get_daily_summary(city=city, target_date=date)
    engine = get_or_create_engine()
    return {
        'city': city,
        'summary': summary,
        'trips': summary.get('trips', []),
        'anomalies': summary.get('anomalies', []),
        'live_telemetry': engine.telemetry
    }


@app.get("/api/trips")
def list_trips(city: Optional[str] = None, date: Optional[str] = None, truck_id: Optional[str] = None):
    return database.get_all_sessions(city=city, target_date=date, truck_id=truck_id)


@app.get("/api/trips/{trip_id}")
def get_trip_detail(trip_id: int):
    detail = database.get_session_detail(trip_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Trip tidak ditemukan")
    return detail


@app.get("/api/anomalies")
def list_anomalies(limit: int = 50):
    return database.get_anomalies(limit=limit)


@app.get("/api/evidence/{filename}")
def get_evidence_video(filename: str):
    # Proteksi sanitasi path
    safe_name = os.path.basename(filename)
    path = os.path.join(config.EVIDENCE_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File video bukti tidak ditemukan")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/engine/status")
def get_engine_status():
    engine = get_or_create_engine()
    return {
        'is_active': is_engine_active,
        'telemetry': engine.telemetry
    }


@app.get("/api/hardware/status")
def get_hardware_status():
    """Status hardware: GPU/CPU, VRAM, RAM, utilization real-time."""
    return hardware.get_summary()


@app.get("/api/storage/status")
def get_storage_status():
    """Status penyimpanan disk dan auto-prune."""
    return security_manager.check_and_prune_disk()


@app.get("/api/cloud/status")
def get_cloud_status():
    """Status sinkronisasi Cloud Database (Supabase / PostgreSQL)."""
    return {
        'is_enabled': cloud_sync.is_enabled,
        'sync_status': cloud_sync.sync_status,
        'last_sync_time': cloud_sync.last_sync_time,
        'synced_state': cloud_sync.state
    }


@app.post("/api/cloud/sync")
def trigger_cloud_sync():
    """Trigger sinkronisasi manual ke cloud."""
    return cloud_sync.sync_now()


class StartEngineRequest(BaseModel):
    source: str = config.VIDEO_SOURCE
    start_minute: float = config.VIDEO_START_MINUTE
    max_frames: int = 0


@app.post("/api/engine/start")
def start_engine(req: StartEngineRequest, _: bool = Depends(verify_api_key)):
    global is_engine_active, engine_thread

    # 1. Rate limiter
    if not _check_rate_limit("engine_start"):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan start engine. Coba lagi nanti.")

    # 2. Input validation & path sanitization
    src = req.source.strip()
    if not src.lower().startswith("rtsp://") and not src.lower().startswith("http://"):
        try:
            resolved = str(pathlib.Path(src).resolve())
        except Exception:
            raise HTTPException(status_code=400, detail="Path sumber video tidak valid.")
        if ".." in req.source:
            raise HTTPException(status_code=400, detail="Path traversal tidak diizinkan.")

    if not (0.0 <= req.start_minute <= 300.0):
        raise HTTPException(status_code=400, detail="start_minute harus berada dalam rentang 0 hingga 300 menit.")

    if is_engine_active:
        return {"status": "already_running", "message": "Engine sudah berjalan"}

    engine_thread = threading.Thread(
        target=background_engine_worker,
        args=(req.source, req.start_minute, req.max_frames),
        daemon=True
    )
    engine_thread.start()
    return {"status": "started", "source": req.source, "start_minute": req.start_minute}


@app.post("/api/engine/stop")
def stop_engine(_: bool = Depends(verify_api_key)):
    global is_engine_active
    engine = get_or_create_engine()
    was_active = is_engine_active
    is_engine_active = False

    if was_active:
        # Catat penghentian ke database
        try:
            database.log_anomaly(
                session_id=engine.current_session_id or 1,
                frame_idx=engine.frame_idx,
                anomaly_type="SYSTEM_ENGINE_STOPPED",
                status="CONFIRMED_THEFT",
                details=f"Proses monitoring dihentikan oleh operator via Dashboard. Total es saat ini: {engine.detector.total} (B:{engine.detector.total_large}, K:{engine.detector.total_small})"
            )
            engine.telegram.send_alert_async(
                title="DETEKSI MONITORING DIHENTIKAN",
                details={
                    'city': config.DEFAULT_CITY,
                    'truck_id': engine.current_truck_id or "-",
                    'trip_number': engine.current_trip_number,
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'message': f"Deteksi dihentikan oleh operator via dashboard. Total es terhitung: {engine.detector.total} (Besar: {engine.detector.total_large}, Kecil: {engine.detector.total_small})."
                }
            )
        except Exception as e:
            logger.error(f"[STOP] Gagal mencatat event stop: {e}")

    return {"status": "stopped", "message": "Perintah berhenti dikirim dan dicatat"}


@app.post("/api/engine/simulate_incident")
def simulate_incident(incident_type: str = "recovered", _: bool = Depends(verify_api_key)):
    """
    Endpoint uji coba untuk memverifikasi logika Anti-False-Positive:
    - 'recovered': es keluar ke samping lalu berhasil masuk ke truk (False positive diatasi)
    - 'theft': es keluar ke samping dan hilang / tidak masuk (Pencurian terkonfirmasi)
    """
    if not _check_rate_limit("simulate"):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan simulasi. Coba lagi nanti.")

    engine = get_or_create_engine()

    if incident_type == "recovered":
        # Simulasikan false positive yang berhasil diatasi
        anom_id = database.log_anomaly(
            session_id=engine.current_session_id or 1,
            frame_idx=engine.frame_idx,
            anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
            status="PENDING",
            details="[SIMULASI] Es terdeteksi tergeser ke samping kiri papan"
        )
        time.sleep(0.5)
        database.update_anomaly(
            anomaly_id=anom_id,
            status="RECOVERED_TO_TRUCK",
            details="[SIMULASI] Pekerja mengembalikan es ke dalam bak truk. Alarm dibatalkan!"
        )
        engine._update_telemetry(
            last_event="Simulasi: Es samping kembali masuk bak (False Alarm dicegah)"
        )
        return {
            "status": "success",
            "type": "recovered",
            "message": "Es keluar ke samping lalu masuk kembali ke truk. Sistem membatalkan alarm!"
        }
    else:
        # Simulasikan pencurian terkonfirmasi
        anom_id = database.log_anomaly(
            session_id=engine.current_session_id or 1,
            frame_idx=engine.frame_idx,
            anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
            status="CONFIRMED_THEFT",
            details="[SIMULASI] Es keluar ke samping kanan dan tidak pernah masuk truk!"
        )
        engine._update_telemetry(
            active_anomalies_count=engine.telemetry['active_anomalies_count'] + 1,
            last_event="🚨 Simulasi: Dugaan pencurian es ke samping terkonfirmasi!"
        )
        # Kirim notifikasi Telegram jika token diset
        engine.telegram.send_alert_async(
            title="DUGAAN PENCURIAN ES TERDETEKSI (SIMULASI)",
            details={
                'city': config.DEFAULT_CITY,
                'truck_id': engine.current_truck_id or "18",
                'trip_number': engine.current_trip_number,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'message': "Es keluar ke samping kanan dan dibawa menjauh dari truk."
            }
        )
        return {
            "status": "success",
            "type": "theft",
            "message": "Pencurian terkonfirmasi! Alert Telegram dikirim dan dicatat ke database."
        }


@app.post("/api/engine/simulate_power_outage")
def api_simulate_power_outage(downtime_minutes: int = 15, _: bool = Depends(verify_api_key)):
    """
    Simulasikan deteksi mati listrik mendadak (sudden blackout) dan auto-recovery:
    - Menghitung durasi pemadaman listrik secara presisi
    - Mencatat insiden ke SQLite lokal & Supabase Cloud
    - Memicu notifikasi darurat Telegram
    """
    if not _check_rate_limit("simulate"):
        raise HTTPException(status_code=429, detail="Terlalu banyak permintaan simulasi. Coba lagi nanti.")

    res = power_watchdog.simulate_power_outage(downtime_minutes=downtime_minutes, cloud_sync_mgr=cloud_sync)
    engine = get_or_create_engine()
    engine._update_telemetry(
        last_event=f"⚡ Listrik mati ({res['downtime']}) pulih kembali!"
    )
    return res


# ===================== WEBSOCKET REAL-TIME =====================

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    engine = get_or_create_engine()
    try:
        while True:
            await websocket.send_json(engine.telemetry)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
    except Exception:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


# ===================== WEB DASHBOARD (HTML) =====================

@app.get("/", response_class=HTMLResponse)
def index_page():
    city_label = config.DEFAULT_CITY.upper()
    branch_code = getattr(config, "BRANCH_CODE", "CABANG")
    html = """
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard Monitoring Loading Es Kristal - __CITY__</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center font-bold text-xl border border-cyan-500/30">
          ❄️
        </div>
        <div>
          <h1 class="font-bold text-lg leading-tight">Sistem Monitoring Es Kristal</h1>
          <p class="text-xs text-slate-400 flex items-center gap-1">
            <span class="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Wilayah: <strong class="text-slate-200">Kota __CITY__ (__BRANCH__)</strong> | AI + Vision Security SOTA
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span id="engineBadge" class="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
          Standby
        </span>
        <button onclick="toggleEngine()" id="btnEngine" class="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-900/30 transition flex items-center gap-2">
          <span>▶</span> Jalankan Deteksi
        </button>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto px-4 py-6 space-y-6">

    <!-- Metrics Cards -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-400 font-medium">Truk Hari Ini</div>
        <div id="statTrucks" class="text-2xl font-bold text-white mt-1">0</div>
        <div class="text-[11px] text-cyan-400 mt-1">Armada Aktif</div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-400 font-medium">Total Trip Loading</div>
        <div id="statTrips" class="text-2xl font-bold text-white mt-1">0</div>
        <div class="text-[11px] text-slate-400 mt-1">Termasuk bolak-balik</div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-400 font-medium">Kemasan Besar</div>
        <div id="statLarge" class="text-2xl font-bold text-amber-400 mt-1">0</div>
        <div class="text-[11px] text-slate-400 mt-1">Kategori >= 14kg</div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-400 font-medium">Kemasan Kecil</div>
        <div id="statSmall" class="text-2xl font-bold text-cyan-400 mt-1">0</div>
        <div class="text-[11px] text-slate-400 mt-1">Kategori ringan</div>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-400 font-medium">Grand Total Es</div>
        <div id="statTotal" class="text-2xl font-bold text-emerald-400 mt-1">0</div>
        <div class="text-[11px] text-emerald-400/80 mt-1">Kantong terhitung</div>
      </div>
    </div>

    <!-- Live Telemetry & Control Banner -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Live Monitoring Card -->
      <div class="lg:col-span-2 bg-slate-800/50 border border-slate-700 rounded-2xl p-5 shadow-lg">
        <div class="flex items-center justify-between pb-4 border-b border-slate-700/80">
          <div>
            <h2 class="font-bold text-base text-slate-100 flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-cyan-400 inline-block animate-ping"></span>
              Live Loading Bay Surveillance
            </h2>
            <p class="text-xs text-slate-400">Monitoring real-time aktivitas muat es ke dalam armada</p>
          </div>
          <div class="text-right">
            <span class="text-xs text-slate-400">Kecepatan Inferensi</span>
            <div id="liveFps" class="text-xs font-mono font-semibold text-emerald-400">10.0 FPS</div>
          </div>
        </div>

        <div class="grid grid-cols-3 gap-4 my-5">
          <div class="bg-slate-900/80 rounded-xl p-3 border border-slate-700/50 text-center">
            <div class="text-xs text-slate-400">Truk Terdeteksi</div>
            <div id="liveTruck" class="text-xl font-bold text-cyan-300 mt-1">-</div>
            <div id="liveTripNum" class="text-[11px] text-slate-400 mt-0.5">Trip #-</div>
          </div>
          <div class="bg-slate-900/80 rounded-xl p-3 border border-slate-700/50 text-center">
            <div class="text-xs text-slate-400">Muatan Sesi Ini</div>
            <div id="liveSessionCount" class="text-xl font-bold text-emerald-300 mt-1">0</div>
            <div id="liveBreakdown" class="text-[11px] text-slate-400 mt-0.5">B:0 | K:0</div>
          </div>
          <div class="bg-slate-900/80 rounded-xl p-3 border border-slate-700/50 text-center">
            <div class="text-xs text-slate-400">Status Pengamanan</div>
            <div id="liveSecurityStatus" class="text-xl font-bold text-emerald-400 mt-1">AMAN</div>
            <div id="liveAnomalies" class="text-[11px] text-slate-400 mt-0.5">0 Insiden</div>
          </div>
        </div>

        <!-- System & Hardware Telemetry Grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div class="bg-slate-900/80 rounded-xl p-2.5 border border-slate-700/50">
            <div class="text-[11px] text-slate-400">Status Stream</div>
            <div id="streamStatus" class="text-slate-400 font-bold text-xs mt-0.5">IDLE</div>
          </div>
          <div class="bg-slate-900/80 rounded-xl p-2.5 border border-slate-700/50">
            <div class="text-[11px] text-slate-400">Status Sabotase</div>
            <div id="tamperStatus" class="text-emerald-400 font-bold text-xs mt-0.5">NORMAL</div>
          </div>
          <div class="bg-slate-900/80 rounded-xl p-2.5 border border-slate-700/50">
            <div class="text-[11px] text-slate-400">Disk Tersisa</div>
            <div id="diskFree" class="text-slate-200 font-bold text-xs mt-0.5">-- GB</div>
          </div>
          <div class="bg-slate-900/80 rounded-xl p-2.5 border border-slate-700/50">
            <div class="text-[11px] text-slate-400">Hardware AI</div>
            <div id="hwDevice" class="text-slate-300 font-mono text-[10px] mt-0.5 truncate">Auto Detect...</div>
          </div>
        </div>

        <div class="bg-slate-950/70 rounded-xl p-4 border border-slate-800 flex items-center justify-between">
          <div>
            <div class="text-xs text-slate-400">Aktivitas Terakhir:</div>
            <div id="liveLastEvent" class="text-sm font-medium text-slate-200 mt-0.5">Sistem siap memproses video</div>
          </div>
          <div id="liveLastTime" class="text-xs font-mono text-slate-400">--:--:--</div>
        </div>
      </div>

      <!-- Testing & Anti-False-Positive Tool -->
      <div class="bg-slate-800/50 border border-slate-700 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
        <div>
          <h2 class="font-bold text-base text-slate-100 flex items-center gap-2">
            🛡️ Anti-False-Positive Test
          </h2>
          <p class="text-xs text-slate-400 mt-1">
            Uji simulasi state machine untuk skenario es ke samping:
          </p>

          <div class="space-y-3 mt-4">
            <button onclick="simulateIncident('recovered')" class="w-full text-left p-3 rounded-xl bg-slate-900/80 hover:bg-slate-900 border border-emerald-500/30 transition group">
              <div class="text-xs font-bold text-emerald-400 flex items-center justify-between">
                <span>1. Ke Samping tapi Balik Masuk</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20">Recovery</span>
              </div>
              <p class="text-[11px] text-slate-400 mt-1">Es tergeser ke samping papan lalu dikembalikan ke dalam bak. Alarm otomatis dibatalkan.</p>
            </button>

            <button onclick="simulateIncident('theft')" class="w-full text-left p-3 rounded-xl bg-slate-900/80 hover:bg-slate-900 border border-rose-500/30 transition group">
              <div class="text-xs font-bold text-rose-400 flex items-center justify-between">
                <span>2. Es Keluar & Hilang (Pencurian)</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-rose-500/20">Theft</span>
              </div>
              <p class="text-[11px] text-slate-400 mt-1">Es dibawa keluar dan tidak pernah masuk truk. Merekam video 10s + kirim alert Telegram.</p>
            </button>

            <button onclick="simulatePowerOutage()" class="w-full text-left p-3 rounded-xl bg-slate-900/80 hover:bg-slate-900 border border-amber-500/30 transition group">
              <div class="text-xs font-bold text-amber-400 flex items-center justify-between">
                <span>3. ⚡ Mati Listrik & Pemulihan</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-amber-500/20">Blackout</span>
              </div>
              <p class="text-[11px] text-slate-400 mt-1">Simulasi pemadaman listrik mendadak pabrik. Hitung durasi padam + kirim trigger Telegram & Supabase.</p>
            </button>
          </div>
        </div>

        <div class="text-xs text-slate-400 border-t border-slate-700/60 pt-3 mt-4">
          Telegram Notifier: <strong class="text-cyan-400">Aktif (Offline Queue Protected)</strong>
        </div>
      </div>
    </div>

    <!-- Table of Trips for Makassar Today -->
    <div class="bg-slate-800/50 border border-slate-700 rounded-2xl p-5 shadow-lg space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="font-bold text-base text-slate-100">Daftar Trip Loading Hari Ini (Makassar)</h2>
          <p class="text-xs text-slate-400">Riwayat loading armada, termasuk truk yang bolak-balik (Trip 1 & 2)</p>
        </div>
        <button onclick="refreshData()" class="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs text-slate-200 transition">
          🔄 Refresh
        </button>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-700 text-slate-400 uppercase font-semibold">
              <th class="py-3 px-3">ID Trip</th>
              <th class="py-3 px-3">Nomor Truk</th>
              <th class="py-3 px-3">Trip Ke-</th>
              <th class="py-3 px-3">Jam Loading In</th>
              <th class="py-3 px-3">Jam Selesai</th>
              <th class="py-3 px-3">Durasi</th>
              <th class="py-3 px-3 text-amber-400">Es Besar</th>
              <th class="py-3 px-3 text-cyan-400">Es Kecil</th>
              <th class="py-3 px-3 text-emerald-400">Total Es</th>
              <th class="py-3 px-3">Status</th>
            </tr>
          </thead>
          <tbody id="tripsTableBody" class="divide-y divide-slate-800 text-slate-200">
            <tr>
              <td colspan="10" class="py-8 text-center text-slate-500">Memuat data riwayat loading...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Anomalies & Evidence Log -->
    <div class="bg-slate-800/50 border border-slate-700 rounded-2xl p-5 shadow-lg space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="font-bold text-base text-slate-100 flex items-center gap-2">
            <span>🚨</span> Log Anomali, Sabotase & Bukti Video
          </h2>
          <p class="text-xs text-slate-400">Deteksi false positive yang dicegah serta insiden pencurian dengan video 10 detik terotentikasi SHA-256</p>
        </div>
      </div>

      <div id="anomaliesList" class="space-y-3">
        <div class="text-xs text-slate-500 text-center py-4">Belum ada catatan anomali.</div>
      </div>
    </div>

  </main>

  <script>
    let isRunning = false;

    async function refreshData() {
      try {
        const res = await fetch('/api/overview');
        const data = await res.json();

        document.getElementById('statTrucks').textContent = data.summary.total_trucks;
        document.getElementById('statTrips').textContent = data.summary.total_trips;
        document.getElementById('statLarge').textContent = data.summary.total_large;
        document.getElementById('statSmall').textContent = data.summary.total_small;
        document.getElementById('statTotal').textContent = data.summary.grand_total;

        renderTrips(data.trips);
        renderAnomalies(data.anomalies);
      } catch (e) {
        console.error("Gagal refresh data:", e);
      }
    }

    function renderTrips(trips) {
      const tbody = document.getElementById('tripsTableBody');
      if (trips.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="py-6 text-center text-slate-500">Belum ada trip tercatat hari ini.</td></tr>';
        return;
      }
      tbody.innerHTML = trips.map(t => {
        const durationMin = Math.round(t.duration_seconds / 60);
        const isDone = t.status === 'COMPLETED';
        const statusBadge = isDone 
          ? '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold">SELESAI</span>'
          : '<span class="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-400 font-semibold animate-pulse">LOADING</span>';

        return `
          <tr class="hover:bg-slate-800/40 transition">
            <td class="py-3 px-3 font-mono text-slate-400">#${t.id}</td>
            <td class="py-3 px-3 font-bold text-slate-100">${t.truck_id}</td>
            <td class="py-3 px-3"><span class="px-2 py-0.5 rounded bg-slate-700 text-slate-300 font-medium">Trip #${t.trip_number}</span></td>
            <td class="py-3 px-3 font-mono text-slate-400">${t.start_time.split('T')[1] || t.start_time}</td>
            <td class="py-3 px-3 font-mono text-slate-400">${t.end_time ? (t.end_time.split('T')[1] || t.end_time) : '-'}</td>
            <td class="py-3 px-3 text-slate-300">${durationMin} menit</td>
            <td class="py-3 px-3 font-semibold text-amber-400">${t.large_count}</td>
            <td class="py-3 px-3 font-semibold text-cyan-400">${t.small_count}</td>
            <td class="py-3 px-3 font-bold text-emerald-400">${t.total_count}</td>
            <td class="py-3 px-3">${statusBadge}</td>
          </tr>
        `;
      }).join('');
    }

    function renderAnomalies(anomalies) {
      const container = document.getElementById('anomaliesList');
      if (anomalies.length === 0) {
        container.innerHTML = '<div class="text-xs text-slate-500 text-center py-4">Belum ada catatan anomali.</div>';
        return;
      }
      container.innerHTML = anomalies.map(a => {
        const isTheft = a.status === 'CONFIRMED_THEFT';
        const isRecovered = a.status === 'RECOVERED_TO_TRUCK';
        let badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 font-bold">PENDING</span>';
        if (isTheft) badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-400 font-bold">🚨 THEFT / TAMPER</span>';
        if (isRecovered) badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 font-bold">✅ RECOVERED (FALSE ALARM DITANGKAL)</span>';

        const videoBtn = a.video_clip_path 
          ? `<a href="/api/evidence/${a.video_clip_path.split(/[\\\\/]/).pop()}" target="_blank" class="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-[11px] font-semibold transition">▶ Tonton Bukti Video</a>`
          : '';

        return `
          <div class="p-3.5 rounded-xl bg-slate-900/70 border border-slate-700/80 flex items-center justify-between">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                ${badge}
                <span class="text-xs font-semibold text-slate-200">Truk #${a.truck_id || '-'} (Trip #${a.trip_number || 1})</span>
                <span class="text-[11px] font-mono text-slate-500">${a.timestamp}</span>
              </div>
              <p class="text-xs text-slate-400">${a.details || '-'}</p>
            </div>
            <div>${videoBtn}</div>
          </div>
        `;
      }).join('');
    }

    async function toggleEngine() {
      const btn = document.getElementById('btnEngine');
      if (!isRunning) {
        btn.textContent = "⏳ Memulai...";
        const res = await fetch('/api/engine/start', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source: 'XVR_ch3_main_20261022200001_20261022203800.mp4', start_minute: 28.5})
        });
        isRunning = true;
        btn.textContent = "⏹ Hentikan Deteksi";
        btn.className = "px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-900/30 transition flex items-center gap-2";
        document.getElementById('engineBadge').textContent = "Processing (Active)";
        document.getElementById('engineBadge').className = "px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
      } else {
        await fetch('/api/engine/stop', {method: 'POST'});
        isRunning = false;
        btn.textContent = "▶ Jalankan Deteksi";
        btn.className = "px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-900/30 transition flex items-center gap-2";
        document.getElementById('engineBadge').textContent = "Standby";
        document.getElementById('engineBadge').className = "px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700";
      }
    }

    async function simulateIncident(type) {
      const res = await fetch(`/api/engine/simulate_incident?incident_type=${type}`, {method: 'POST'});
      const data = await res.json();
      alert(data.message);
      refreshData();
    }

    async function simulatePowerOutage() {
      const res = await fetch(`/api/engine/simulate_power_outage?downtime_minutes=15`, {method: 'POST'});
      const data = await res.json();
      alert(`[MATI LISTRIK] ${data.details}`);
      refreshData();
    }

    // Connect WebSocket Telemetry
    function connectWS() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/telemetry`);
      
      ws.onmessage = (event) => {
        const tel = JSON.parse(event.data);
        document.getElementById('liveTruck').textContent = tel.truck_id !== '-' ? `Truk ${tel.truck_id}` : '-';
        document.getElementById('liveTripNum').textContent = `Trip #${tel.trip_number}`;
        document.getElementById('liveSessionCount').textContent = tel.count_total;
        document.getElementById('liveBreakdown').textContent = `B:${tel.count_large} | K:${tel.count_small}`;
        document.getElementById('liveFps').textContent = `${tel.fps} FPS`;
        document.getElementById('liveLastEvent').textContent = tel.last_event;
        document.getElementById('liveLastTime').textContent = tel.last_event_time;
        document.getElementById('liveAnomalies').textContent = `${tel.active_anomalies_count} Insiden`;
        
        if (tel.active_anomalies_count > 0) {
          document.getElementById('liveSecurityStatus').textContent = "WASPADA";
          document.getElementById('liveSecurityStatus').className = "text-xl font-bold text-rose-400 mt-1 animate-pulse";
        } else {
          document.getElementById('liveSecurityStatus').textContent = "AMAN";
          document.getElementById('liveSecurityStatus').className = "text-xl font-bold text-emerald-400 mt-1";
        }

        // Update Stream, Tampering, Disk & Hardware
        if (document.getElementById('streamStatus')) {
          const streamEl = document.getElementById('streamStatus');
          const tst = tel.stream_status || 'IDLE';
          streamEl.textContent = tst;
          streamEl.className = tst === 'CONNECTED' ? 'text-emerald-400 font-bold text-xs mt-0.5' :
                               tst === 'RECONNECTING' ? 'text-amber-400 font-bold text-xs mt-0.5' :
                               tst === 'DISCONNECTED' ? 'text-rose-400 font-bold text-xs mt-0.5 animate-pulse' : 'text-slate-400 font-bold text-xs mt-0.5';
        }
        if (document.getElementById('tamperStatus')) {
          const tamperEl = document.getElementById('tamperStatus');
          const tmpr = tel.tamper_status || 'NORMAL';
          tamperEl.textContent = tmpr;
          tamperEl.className = tmpr !== 'NORMAL' ? 'text-rose-500 font-bold text-xs mt-0.5 animate-pulse' : 'text-emerald-400 font-bold text-xs mt-0.5';
        }
        if (document.getElementById('diskFree')) {
          const df = tel.disk_free_gb || 0;
          document.getElementById('diskFree').textContent = df > 0 ? `${df.toFixed(1)} GB` : '-- GB';
        }
        if (document.getElementById('hwDevice')) {
          document.getElementById('hwDevice').textContent = tel.hardware_name || tel.hardware_device || '-';
        }

        if (tel.is_running && !isRunning) {
          isRunning = true;
          document.getElementById('btnEngine').textContent = "⏹ Hentikan Deteksi";
          document.getElementById('engineBadge').textContent = "Processing (Active)";
        }
      };

      ws.onclose = () => {
        setTimeout(connectWS, 2000);
      };
    }

    // Initialize
    refreshData();
    connectWS();
    setInterval(refreshData, 3000);
  </script>
</body>
</html>
    """
    return html.replace("__CITY__", city_label).replace("__BRANCH__", branch_code)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=config.API_HOST, port=config.API_PORT, reload=False)
