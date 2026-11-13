import os
import sys
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
for _sub in ("core", "services", "scripts"):
    _p = os.path.join(ROOT_DIR, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROFILE_FILE = "data/branch_profile.json"
_branch_data = {}
if os.path.exists(PROFILE_FILE):
    try:
        with open(PROFILE_FILE, "r") as f:
            _branch_data = json.load(f)
    except Exception:
        pass

DEFAULT_CITY = os.getenv("BRANCH_CITY", _branch_data.get("branch_city", "Makassar"))
BRANCH_CODE = os.getenv("BRANCH_CODE", _branch_data.get("branch_code", "MKS-01"))
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", _branch_data.get("video_source", "videos/XVR_ch3_main_20261022200001_20261022203800.mp4"))
VIDEO_START_MINUTE = float(_branch_data.get("video_start_minute", 28.5))

DETECTION_MODE = os.getenv("DETECTION_MODE", "yolo")
YOLO_WEIGHTS_PATH = "weights/yolo_ice_best.pt"
YOLO_CONF_THRESH = 0.25

ROI = (420, 1050, 280, 370)
TRIPWIRE_Y = 120
TRIPWIRE_COLOR_IDLE = (0, 255, 0)
TRIPWIRE_COLOR_ACTIVE = (0, 0, 255)

SIZE_THRESHOLD_AREA = 14000
MIN_PACKAGE_AREA = 2500
MAX_PACKAGE_AREA = 38000

TRUCK_ROI = (220, 650, 480, 450)
TRUCK_PRESENCE_THRESHOLD = 15000
TRUCK_CONFIRM_FRAMES = 10
TRUCK_GONE_FRAMES = 50
OCR_CONFIDENCE_MIN = 0.5

TRACKER_MAX_DISTANCE = 120
TRACKER_MAX_MISSING = 10
TRACKER_MIN_HITS = 2
COUNTING_COOLDOWN_FRAMES = 24

CHUTE_MIN_X = 400
CHUTE_MAX_X = 720
TRUCK_MIN_X = 220
TRUCK_MAX_X = 750
TRUCK_ENTRANCE_Y = 1050
SIDE_RECOVERY_WINDOW_FRAMES = 35

SIDE_LOST_FRAMES = 100
SIDE_MAX_DWELL_FRAMES = 600
SIDE_RECOVERY_RADIUS_FRAC = 0.25

COUNT_MIN_X = 380
COUNT_MAX_X = 740
COUNT_ENTRY_MIN_X = 220
COUNT_ENTRY_MAX_X = 750
COUNT_RULES = ((1260, 5), (1220, 3))
COUNT_ENTRY_MIN_DY = 2
DIRECT_THROW_MIN_HITS = 2
STATIONARY_REID_RADIUS_PX = 55
STATIONARY_REID_FRAMES = 60
CONTINUATION_REID_FRAMES = 12
DETECTION_MIN_X = 200
DETECTION_MAX_X = 1100
STACKED_AREA_PX = 55000
SMALL_AREA_PX = 12000

CAMERA_PROFILE = os.getenv("CAMERA_PROFILE", _branch_data.get("camera_profile", "cam3")).lower()
CAMERA_PROFILES = {
    "cam3": {
        "ROI": (420, 1050, 280, 370),
        "TRIPWIRE_Y": 120,
        "CHUTE_MIN_X": 400,
        "CHUTE_MAX_X": 720,
        "TRUCK_MIN_X": 220,
        "TRUCK_MAX_X": 750,
        "TRUCK_ENTRANCE_Y": 1050,
        "COUNT_MIN_X": 380,
        "COUNT_MAX_X": 740,
        "COUNT_ENTRY_MIN_X": 220,
        "COUNT_ENTRY_MAX_X": 750,
        "COUNT_RULES": ((1260, 5), (1220, 3)),
        "COUNT_ENTRY_MIN_DY": 2,
        "DETECTION_MIN_X": 200,
        "DETECTION_MAX_X": 1100,
        "STACKED_AREA_PX": 55000,
        "SMALL_AREA_PX": 12000,
    },
    "cam10": {
        "ROI": (640, 620, 220, 520),
        "TRIPWIRE_Y": 120,
        "CHUTE_MIN_X": 640,
        "CHUTE_MAX_X": 845,
        "TRUCK_MIN_X": 630,
        "TRUCK_MAX_X": 875,
        "TRUCK_ENTRANCE_Y": 680,
        "COUNT_MIN_X": 640,
        "COUNT_MAX_X": 845,
        "COUNT_ENTRY_MIN_X": 630,
        "COUNT_ENTRY_MAX_X": 875,
        "COUNT_RULES": ((900, 25), (820, 6), (740, 3)),
        "COUNT_ENTRY_MIN_DY": 2,
        "DETECTION_MIN_X": 560,
        "DETECTION_MAX_X": 1150,
        "STACKED_AREA_PX": 210000,
        "SMALL_AREA_PX": 15000,
    },
}

def apply_camera_profile(profile_name: str):
    key = profile_name.lower()
    if key not in CAMERA_PROFILES:
        raise ValueError(f"CAMERA_PROFILE tidak dikenal: {profile_name} (pilihan: {list(CAMERA_PROFILES)})")
    globals()["CAMERA_PROFILE"] = key
    globals().update(CAMERA_PROFILES[key])

def auto_select_camera_profile(frame_w: int, frame_h: int) -> str:
    if frame_w <= 0 or frame_h <= 0:
        return CAMERA_PROFILE
    ratio = frame_w / float(frame_h)
    target = "cam10" if ratio >= 0.78 else "cam3"
    if CAMERA_PROFILE != target:
        apply_camera_profile(target)
    return CAMERA_PROFILE

apply_camera_profile(CAMERA_PROFILE)

EVIDENCE_DIR = "data/evidence"
EVIDENCE_PRE_SECONDS = 5.0
EVIDENCE_POST_SECONDS = 5.0

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLE_ALERTS = True

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = 8000
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "True").lower() in ("true", "1")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()]

MAX_DISK_USAGE_PERCENT = 85.0
EVIDENCE_RETENTION_DAYS = 30
TAMPERING_GUARD_ENABLED = True
AUTO_HARDWARE_DETECTION = True

DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720
SHOW_PREVIEW = True
SHOW_ROI_BOX = True
SHOW_TRIPWIRE = True

SAVE_SNAPSHOTS = True
SNAPSHOT_DIR = "data/snapshots"
DB_PATH = "data/sessions.db"

CLOUD_SYNC_ENABLED = os.getenv("CLOUD_SYNC_ENABLED", "True").lower() in ("true", "1")
CLOUD_DATABASE_URL = os.getenv("CLOUD_DATABASE_URL", "")
CLOUD_SUPABASE_URL = os.getenv("CLOUD_SUPABASE_URL", "")
CLOUD_SUPABASE_KEY = os.getenv("CLOUD_SUPABASE_KEY", "")
CLOUD_SYNC_INTERVAL_SEC = int(os.getenv("CLOUD_SYNC_INTERVAL_SEC", "10"))

LOG_DIR = "data/logs"
LOG_LEVEL = "INFO"
