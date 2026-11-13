import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("API_SECRET_KEY", "test-secret")

import pytest
from fastapi import HTTPException
import config
import database
import security

@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from engine import IceDetectionEngine

    class FakeEvidence:
        def trigger_recording(self, **kw): return ""
    class FakeTelegram:
        def send_alert_async(self, **kw): pass

    e = object.__new__(IceDetectionEngine)
    e.city, e.branch_code = "Makassar", "MKS-01"
    e.current_session_id = 1
    e.current_truck_id, e.current_trip_number = "T1", 1
    e.frame_idx = 0
    e.pending_side_objects = {}
    e.telemetry = {"active_anomalies_count": 0}
    e.evidence_recorder, e.telegram = FakeEvidence(), FakeTelegram()
    e.detector = type("D", (), {"tracker": type("T", (), {"objects": {}})()})()
    monkeypatch.setattr(database, "log_anomaly", lambda **kw: 7)
    monkeypatch.setattr(database, "update_anomaly", lambda *a, **kw: None)
    monkeypatch.setattr(database, "delete_anomaly", lambda *a, **kw: None)
    return e

def _step(e, n=1):
    for _ in range(n):
        e.frame_idx += 1
        e._check_side_exit_and_anomalies(None)

def test_side_exit_then_recovery_is_not_theft(engine):
    engine.detector.tracker.objects = {1: {"centroid": (config.CHUTE_MIN_X - 50, config.TRUCK_ENTRANCE_Y + 40)}}
    _step(engine)
    assert 1 in engine.pending_side_objects
    engine.detector.tracker.objects = {1: {"centroid": (500, config.TRUCK_ENTRANCE_Y - 50)}}
    _step(engine)
    assert not engine.pending_side_objects
    assert engine.telemetry["active_anomalies_count"] == 0

def test_side_exit_never_returns_is_theft(engine):
    engine.detector.tracker.objects = {1: {"centroid": (config.CHUTE_MAX_X + 50, config.TRUCK_ENTRANCE_Y + 40)}}
    _step(engine)
    engine.detector.tracker.objects = {}
    _step(engine, config.SIDE_LOST_FRAMES - 2)
    assert engine.telemetry["active_anomalies_count"] == 0
    _step(engine, 5)
    assert engine.telemetry["active_anomalies_count"] == 1

def test_visible_in_side_short_time_no_alarm_long_time_alarm(engine):
    pos = (config.CHUTE_MAX_X + 50, config.TRUCK_ENTRANCE_Y + 40)
    engine.detector.tracker.objects = {1: {"centroid": pos}}
    _step(engine, 150)
    assert engine.telemetry["active_anomalies_count"] == 0
    _step(engine, config.SIDE_MAX_DWELL_FRAMES)
    assert engine.telemetry["active_anomalies_count"] == 1

def test_recovery_with_new_id_near_origin_cancels_alarm(engine):
    side = (config.CHUTE_MAX_X + 50, config.TRUCK_ENTRANCE_Y + 40)
    engine.detector.tracker.objects = {1: {"centroid": side}}
    _step(engine, 5)
    engine.detector.tracker.objects = {}
    _step(engine, 30)
    engine.detector.tracker.objects = {2: {"centroid": (config.CHUTE_MAX_X - 100, config.TRUCK_ENTRANCE_Y + 20),
                                           "origin": (side[0] - 30, side[1] - 20)}}
    _step(engine)
    assert not engine.pending_side_objects
    engine.detector.tracker.objects = {}
    _step(engine, config.SIDE_LOST_FRAMES + 20)
    assert engine.telemetry["active_anomalies_count"] == 0

def test_unrelated_new_ice_far_from_side_does_not_cancel_alarm(engine):
    side = (config.CHUTE_MAX_X + 50, config.TRUCK_ENTRANCE_Y + 40)
    engine.detector.tracker.objects = {1: {"centroid": side}}
    _step(engine, 5)
    engine.detector.tracker.objects = {2: {"centroid": (500, config.TRUCK_ENTRANCE_Y - 100),
                                           "origin": (500, config.TRUCK_ENTRANCE_Y - 400)}}
    _step(engine, 10)
    assert engine.pending_side_objects
    engine.detector.tracker.objects = {}
    _step(engine, config.SIDE_LOST_FRAMES + 5)
    assert engine.telemetry["active_anomalies_count"] == 1

def test_id_switch_while_in_side_does_not_create_duplicate_anomaly(engine, monkeypatch):
    calls = []
    monkeypatch.setattr(database, "log_anomaly", lambda **kw: calls.append(kw) or 7)
    p = (config.CHUTE_MAX_X + 50, config.TRUCK_ENTRANCE_Y + 40)
    engine.detector.tracker.objects = {1: {"centroid": p}}
    _step(engine, 3)
    engine.detector.tracker.objects = {2: {"centroid": (p[0] + 10, p[1] + 5)}}
    _step(engine, 3)
    assert len(calls) == 1
    assert list(engine.pending_side_objects) == [2]

def test_brief_tracking_loss_does_not_trigger_immediately(engine):
    engine.detector.tracker.objects = {1: {"centroid": (config.CHUTE_MIN_X - 50, config.TRUCK_ENTRANCE_Y + 40)}}
    _step(engine)
    engine.detector.tracker.objects = {}
    _step(engine, 3)
    assert engine.telemetry["active_anomalies_count"] == 0

def test_engine_has_branch_code_attribute():
    import inspect, engine as eng
    assert "self.branch_code" in inspect.getsource(eng.IceDetectionEngine.__init__)

def test_api_key_fail_closed(monkeypatch):
    monkeypatch.setattr(config, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(config, "API_SECRET_KEY", "abc")
    assert security.verify_api_key("abc") is True
    for bad in ("", "wrong", "ice_admin_token"):
        with pytest.raises(HTTPException):
            security.verify_api_key(bad)
    monkeypatch.setattr(config, "API_SECRET_KEY", "")
    with pytest.raises(HTTPException):
        security.verify_api_key("")

@pytest.fixture
def dummy_detector():
    from detector import PureYOLOPackageDetector
    d = object.__new__(PureYOLOPackageDetector)
    d.total_large = 0
    d.total_small = 0
    d.counted_ids = set()
    d.counted_at_frame = {}
    d.tracker_history = {}
    d.last_seen_frame = {}
    d.active_objects = {}
    d.tripwire_flash = 0
    d.last_counted_frame = -999
    d.count_cooldown_frames = 8
    d._frame_counter = 0
    return d

def test_count_all_three_entry_paths(dummy_detector):
    d = dummy_detector
    mid_x = (config.COUNT_MIN_X + config.COUNT_MAX_X) // 2
    tw = d.tripwire_y

    d._frame_counter = 1
    assert d._record_and_should_count(1, mid_x, tw + 20) is False
    d._frame_counter = 2
    assert d._record_and_should_count(1, mid_x, tw - 5) is True

    d._frame_counter = 20
    assert d._record_and_should_count(2, config.CHUTE_MAX_X + 80, tw + 60) is False
    d._frame_counter = 21
    assert d._record_and_should_count(2, mid_x, config.TRUCK_ENTRANCE_Y - 10) is True

    d._frame_counter = 40
    assert d._record_and_should_count(3, mid_x, config.TRUCK_ENTRANCE_Y - 20) is False
    d._frame_counter = 41
    assert d._record_and_should_count(3, mid_x, config.TRUCK_ENTRANCE_Y - 25) is True

def test_stationary_bag_at_truck_entrance_id_switch_not_double_counted(dummy_detector):
    d = dummy_detector
    mid_x = (config.COUNT_MIN_X + config.COUNT_MAX_X) // 2
    ey = config.TRUCK_ENTRANCE_Y - 15

    for step, y in enumerate([ey + 10, ey, ey, ey, ey], start=1):
        d._frame_counter = step
        res = d._record_and_should_count(10, mid_x, y)
        if step == 2:
            assert res is True
        else:
            assert res is False

    d._frame_counter = 25
    assert d._record_and_should_count(11, mid_x + 8, ey + 4) is False
    d._frame_counter = 26
    assert d._record_and_should_count(11, mid_x + 6, ey) is False

def test_auto_select_camera_profile():
    assert config.auto_select_camera_profile(1440, 1616) == "cam10"
    assert config.CHUTE_MIN_X == 640
    assert config.TRUCK_ENTRANCE_Y == 680

    assert config.auto_select_camera_profile(1296, 1944) == "cam3"
    assert config.CHUTE_MIN_X == 400
    assert config.TRUCK_ENTRANCE_Y == 1050
