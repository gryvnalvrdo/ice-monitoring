import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("API_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient

import config
import database
import security
import server


class _DummyDetector:
    total_large = 1
    total_small = 2
    total = 3


class _DummyEngine:
    def __init__(self):
        self.video_source = "rtsp://admin:Rahasia99@192.168.1.55:554/cam3"
        self.city = "Makassar"
        self.current_session_id = 1
        self.current_truck_id = "B1234XX"
        self.current_trip_number = 1
        self.frame_idx = 10
        self.is_running = False
        self.detector = _DummyDetector()
        self.telemetry = {
            "is_running": False,
            "fps": 0.0,
            "frame_idx": 10,
            "camera_profile": "cam3",
            "truck_present": True,
            "truck_id": "B1234XX",
            "trip_number": 1,
            "city": "Makassar",
            "count_large": 1,
            "count_small": 2,
            "count_total": 3,
            "active_anomalies_count": 0,
            "pending_side_count": 0,
            "last_event": "Es masuk",
            "last_event_time": "10:00:00",
            "last_active_at": "2026-11-13 10:00:00",
            "stream_status": "IDLE",
            "tamper_status": "NORMAL",
            "disk_free_gb": 50.0,
            "hardware_device": "cpu",
            "hardware_name": "CPU",
            "recent_counts": [],
            "recent_recoveries": [],
        }
        self.telegram = type("TG", (), {"send_alert_async": lambda *a, **kw: None})()

    def _update_telemetry(self, **kwargs):
        self.telemetry.update(kwargs)

    def get_latest_jpeg(self):
        return b"\xff\xd8\xff\xd9"


@pytest.fixture
def web_client(monkeypatch, tmp_path):
    db_file = str(tmp_path / "web_test.db")
    ev_dir = str(tmp_path / "evidence")
    snap_dir = str(tmp_path / "snapshots")
    log_dir = str(tmp_path / "logs")
    os.makedirs(ev_dir, exist_ok=True)
    os.makedirs(snap_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    monkeypatch.setattr(database, "DB_PATH", db_file)
    monkeypatch.setattr(config, "EVIDENCE_DIR", ev_dir)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", snap_dir)
    monkeypatch.setattr(config, "LOG_DIR", log_dir)
    monkeypatch.setattr(security.security_manager, "evidence_dir", ev_dir)
    monkeypatch.setattr(config, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", security.hash_password("AdminPass!123"))
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    monkeypatch.setattr(config, "OPERATOR_USERNAME", "operator")
    monkeypatch.setattr(config, "OPERATOR_PASSWORD_HASH", security.hash_password("OpPass!123"))
    monkeypatch.setattr(config, "OPERATOR_PASSWORD", "")
    monkeypatch.setattr(config, "API_SECRET_KEY", "test-secret")
    monkeypatch.setattr(config, "ALLOW_SIMULATION", False)
    monkeypatch.setattr(config, "LOGIN_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(config, "LOGIN_LOCKOUT_SECONDS", 120)
    monkeypatch.setattr(config, "VIDEO_SOURCE", "rtsp://admin:Rahasia99@192.168.1.55:554/cam3")

    security.session_manager.clear_all()
    security.login_rate_limiter._records.clear()
    server.is_engine_active = False
    server.global_engine = _DummyEngine()

    database.init_db()
    return TestClient(server.app)


def _login(client: TestClient, username: str, password: str):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    return res


def test_forced_browsing_blocked_everywhere(web_client):
    r_home = web_client.get("/", follow_redirects=False)
    assert r_home.status_code == 302
    assert r_home.headers["location"] == "/login"
    assert "no-store" in r_home.headers.get("cache-control", "")

    protected = [
        "/api/overview",
        "/api/trips",
        "/api/trips/1",
        "/api/anomalies",
        "/api/cameras",
        "/api/reports/export",
        "/api/engine/status",
        "/api/hardware/status",
        "/api/storage/status",
        "/api/cloud/status",
        "/api/evidence/clip.mp4",
        "/api/snapshots/snap.jpg",
        "/api/stream/live",
        "/assets/dashboard.js",
    ]
    for path in protected:
        resp = web_client.get(path)
        assert resp.status_code == 401, f"{path} tidak terlindungi"

    for doc_path in ("/docs", "/redoc", "/openapi.json"):
        assert web_client.get(doc_path).status_code == 404

    with pytest.raises(Exception):
        with web_client.websocket_connect("/ws/telemetry"):
            pass


def test_login_bruteforce_lockout_and_fail_closed(web_client, monkeypatch):
    r1 = _login(web_client, "admin", "salah1")
    assert r1.status_code == 401
    r2 = _login(web_client, "admin", "salah2")
    assert r2.status_code == 401
    r3 = _login(web_client, "admin", "salah3")
    assert r3.status_code == 429

    r4 = _login(web_client, "admin", "AdminPass!123")
    assert r4.status_code == 429

    security.login_rate_limiter._records.clear()
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    monkeypatch.setattr(config, "OPERATOR_PASSWORD_HASH", "")
    monkeypatch.setattr(config, "OPERATOR_PASSWORD", "")
    monkeypatch.setattr(config, "API_SECRET_KEY", "")
    assert _login(web_client, "admin", "AdminPass!123").status_code == 503


def test_session_cookie_logout_and_back_prevention(web_client):
    res = _login(web_client, "admin", "AdminPass!123")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "admin"
    csrf = data["csrf_token"]

    set_cookie = res.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    ok_page = web_client.get("/", follow_redirects=False)
    assert ok_page.status_code == 200
    assert "no-store" in ok_page.headers.get("cache-control", "")
    assert web_client.get("/api/overview").status_code == 200

    assert web_client.post("/api/auth/logout").status_code == 403

    out = web_client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert out.status_code == 200

    assert web_client.get("/api/overview").status_code == 401
    assert web_client.get("/", follow_redirects=False).status_code == 302


def test_rbac_operator_vs_admin_and_csrf_origin(web_client, monkeypatch):
    op = _login(web_client, "operator", "OpPass!123")
    assert op.status_code == 200
    op_csrf = op.json()["csrf_token"]
    assert op.json()["role"] == "operator"

    assert web_client.get("/api/overview").status_code == 200
    assert web_client.post("/api/engine/stop", headers={"X-CSRF-Token": op_csrf}).status_code == 403
    assert web_client.post("/api/camera/select", json={"camera_profile": "cam10"}, headers={"X-CSRF-Token": op_csrf}).status_code == 403

    web_client.post("/api/auth/logout", headers={"X-CSRF-Token": op_csrf})

    adm = _login(web_client, "admin", "AdminPass!123")
    adm_csrf = adm.json()["csrf_token"]

    assert web_client.post("/api/camera/select", json={"camera_profile": "cam10"}).status_code == 403
    assert web_client.post(
        "/api/camera/select",
        json={"camera_profile": "cam10"},
        headers={"X-CSRF-Token": adm_csrf, "Origin": "https://attacker.example"},
    ).status_code == 403

    ok_cam = web_client.post(
        "/api/camera/select",
        json={"camera_profile": "cam10"},
        headers={"X-CSRF-Token": adm_csrf},
    )
    assert ok_cam.status_code == 200
    assert config.CAMERA_PROFILE == "cam10"

    config.apply_camera_profile("cam3")


def test_ssrf_path_traversal_rtsp_mask_and_simulation_blocked(web_client):
    adm = _login(web_client, "admin", "AdminPass!123")
    csrf = adm.json()["csrf_token"]

    cams = web_client.get("/api/cameras").json()
    ov = web_client.get("/api/overview").json()
    assert "Rahasia99" not in str(cams)
    assert "Rahasia99" not in str(ov)
    assert "rtsp://***@192.168.1.55:554/cam3" in str(cams)

    bad_sources = [
        "http://169.254.169.254/latest/meta-data",
        "https://evil.com/stream.mp4",
        "file:///etc/passwd",
        "rtsp://127.0.0.1:554/stream",
        "rtsp://localhost/cam",
        "../../.env",
        "server.py",
    ]
    for bad in bad_sources:
        r = web_client.post(
            "/api/engine/start",
            json={"source": bad, "start_minute": 0.0},
            headers={"X-CSRF-Token": csrf},
        )
        assert r.status_code == 400, f"Sumber berbahaya tidak ditolak: {bad}"

    assert web_client.get("/api/evidence/bad.exe").status_code == 400
    assert web_client.get("/api/snapshots/bad.exe").status_code == 400
    assert web_client.get("/api/evidence/..%2F..%2F.env").status_code in (400, 404)

    assert web_client.post("/api/engine/simulate_incident", headers={"X-CSRF-Token": csrf}).status_code == 403
    assert web_client.post("/api/engine/simulate_power_outage", headers={"X-CSRF-Token": csrf}).status_code == 403


def test_anomaly_classification_and_csv_formula_sanitization(web_client):
    sid = database.create_session("=CMD|'/C calc'!A0", "=CMD", city="Makassar")
    database.log_package(sid, "large", 20000, 10, trajectory="papan")
    database.log_package(sid, "small", 9000, 20, trajectory="lempar_langsung")
    database.close_session(sid, duration_sec=65)

    database.log_anomaly(sid, 30, "CAMERA_DISCONNECTED", "CONFIRMED_THEFT", details="Kabel putus", city="Makassar")
    database.log_anomaly(sid, 40, "SYSTEM_ENGINE_STOPPED", "CONFIRMED_THEFT", details="Admin stop", city="Makassar")
    database.log_anomaly(sid, 50, "SUSPECTED_THEFT_SIDE_EXIT", "RECOVERED_TO_TRUCK", details="Batal", city="Makassar")
    database.log_anomaly(sid, 60, "SUSPECTED_THEFT_SIDE_EXIT", "CONFIRMED_THEFT", details="Hilang", city="Makassar")

    _login(web_client, "operator", "OpPass!123")

    ov = web_client.get("/api/overview").json()
    assert ov["stats"]["theft_count"] == 1
    assert ov["stats"]["camera_issue_count"] == 2
    assert ov["stats"]["recovered_count"] == 1

    csv_resp = web_client.get("/api/reports/export")
    assert csv_resp.status_code == 200
    assert "'=CMD|'/C calc'!A0" in csv_resp.text


def test_frontend_has_no_innerhtml_sinks():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("dashboard.js", "login.js"):
        with open(os.path.join(root, "web", name), "r", encoding="utf-8") as f:
            content = f.read()
        assert "innerHTML" not in content
        assert "outerHTML" not in content
        assert "document.write" not in content


def test_security_headers_trip_detail_and_authenticated_websocket(web_client):
    sid = database.create_session("B9999AA", "B9999AA", city="Makassar")
    database.log_package(sid, "large", 19000, 10, trajectory="papan")
    database.log_package(sid, "small", 8000, 20, trajectory="samping_kembali")

    _login(web_client, "operator", "OpPass!123")

    page = web_client.get("/")
    assert page.status_code == 200
    assert page.headers.get("x-frame-options") == "DENY"
    assert page.headers.get("x-content-type-options") == "nosniff"
    assert "script-src 'self'" in page.headers.get("content-security-policy", "")

    detail = web_client.get(f"/api/trips/{sid}")
    assert detail.status_code == 200
    trajs = [e["trajectory_type"] for e in detail.json()["events"]]
    assert trajs == ["papan", "samping_kembali"]

    with web_client.websocket_connect("/ws/telemetry") as ws:
        msg = ws.receive_json()
        assert msg["truck_id"] == "B1234XX"
        assert "Rahasia99" not in str(msg)


def test_evidence_retention_auto_delete_keeps_db_records(web_client, monkeypatch):
    import time
    monkeypatch.setattr(config, "EVIDENCE_RETENTION_DAYS", 30)
    monkeypatch.setattr(config, "SNAPSHOT_RETENTION_DAYS", 7)

    old_vid = os.path.join(config.EVIDENCE_DIR, "old_clip.mp4")
    new_vid = os.path.join(config.EVIDENCE_DIR, "new_clip.mp4")
    old_snap = os.path.join(config.SNAPSHOT_DIR, "old_snap.jpg")
    for p in (old_vid, new_vid, old_snap):
        with open(p, "wb") as f:
            f.write(b"12345")

    now = time.time()
    os.utime(old_vid, (now - 35 * 86400, now - 35 * 86400))
    os.utime(old_snap, (now - 10 * 86400, now - 10 * 86400))

    sid = database.create_session("B7777CC", "B7777CC", city="Makassar")
    anom_id = database.log_anomaly(
        sid, 10, "SUSPECTED_THEFT_SIDE_EXIT", "CONFIRMED_THEFT",
        video_clip_path=old_vid, details="Hilang", city="Makassar"
    )
    assert anom_id > 0

    res = security.security_manager.check_and_prune_disk()
    assert res["pruned_expired_count"] == 1
    assert res["pruned_snapshots_count"] == 1
    assert not os.path.exists(old_vid)
    assert not os.path.exists(old_snap)
    assert os.path.exists(new_vid)

    _login(web_client, "operator", "OpPass!123")
    ov = web_client.get("/api/overview").json()
    assert len(ov["anomalies"]) == 1
    assert ov["anomalies"][0]["video_available"] is False


def test_system_anomaly_without_session_visible_and_cloud_sanitized(web_client, monkeypatch):
    import cloud_sync as cs_mod
    database.log_anomaly(
        None, 0, "CAMERA_DISCONNECTED", "CONFIRMED_THEFT",
        details="Kabel putus saat idle", city="Makassar"
    )
    database.log_anomaly(
        999999, 5, "SYSTEM_ENGINE_STOPPED", "CONFIRMED_THEFT",
        details="Orphan session id", city="Makassar"
    )

    _login(web_client, "operator", "OpPass!123")
    ov = web_client.get("/api/overview").json()
    assert ov["stats"]["camera_issue_count"] == 2

    pushed = []
    mgr = cs_mod.CloudSyncManager(supabase_url="https://x.supabase.co", supabase_key="k", interval_sec=10)
    monkeypatch.setattr(mgr, "_push_to_supabase", lambda table, recs: pushed.append((table, recs)) or True)
    sync_res = mgr.sync_now()
    assert sync_res["status"] == "success"
    anom_batches = [recs for table, recs in pushed if table == "anomalies"]
    assert len(anom_batches) == 1
    for rec in anom_batches[0]:
        assert rec["session_id"] is None
