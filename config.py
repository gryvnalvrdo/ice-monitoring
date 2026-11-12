import os
import json

# Profil Cabang Pabrik (Multi-Branch Support)
# Otomatis dimuat dari data/branch_profile.json jika cabang baru disetup
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
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", _branch_data.get("video_source", "XVR_ch3_main_20261022200001_20261022203800.mp4"))
VIDEO_START_MINUTE = float(_branch_data.get("video_start_minute", 28.5))

# Model Deteksi AI & YOLO
DETECTION_MODE = os.getenv("DETECTION_MODE", "yolo")  # Pilihan: 'yolo', 'opencv', 'hybrid'
YOLO_WEIGHTS_PATH = "weights/yolo_ice_best.pt"
YOLO_CONF_THRESH = 0.25

# Zona Papan Luncur (Chute)
ROI = (420, 1050, 280, 370)
TRIPWIRE_Y = 120

TRIPWIRE_COLOR_IDLE = (0, 255, 0)
TRIPWIRE_COLOR_ACTIVE = (0, 0, 255)

# Klasifikasi Ukuran Kemasan
SIZE_THRESHOLD_AREA = 14000
MIN_PACKAGE_AREA = 2500
MAX_PACKAGE_AREA = 38000

# Deteksi Truk & OCR
TRUCK_ROI = (220, 650, 480, 450)
TRUCK_PRESENCE_THRESHOLD = 15000
TRUCK_CONFIRM_FRAMES = 10
TRUCK_GONE_FRAMES = 50
OCR_CONFIDENCE_MIN = 0.5

# Tracking & Cooldown
TRACKER_MAX_DISTANCE = 120
TRACKER_MAX_MISSING = 10
TRACKER_MIN_HITS = 2
COUNTING_COOLDOWN_FRAMES = 24

# Zona Operasional & Anti-False-Positive
DEFAULT_CITY = "Makassar"
CHUTE_MIN_X = 400
CHUTE_MAX_X = 720
TRUCK_ENTRANCE_Y = 1050       # y <= 1050 dianggap sudah masuk area bak truk
SIDE_RECOVERY_WINDOW_FRAMES = 35 # ~3.5 detik toleransi es ke samping tapi balik ke truk

# Rekaman Bukti Video (Circular Buffer)
EVIDENCE_DIR = "data/evidence"
EVIDENCE_PRE_SECONDS = 5.0
EVIDENCE_POST_SECONDS = 5.0

# Notifikasi Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLE_ALERTS = True

# Server API & Web Dashboard
API_HOST = "0.0.0.0"
API_PORT = 8000
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "ice_secure_2026_admin")
REQUIRE_API_KEY = False  # Set True untuk mode produksi ketat

# Keamanan Sistem, Storage & Stream Guard (SOTA)
MAX_DISK_USAGE_PERCENT = 85.0
EVIDENCE_RETENTION_DAYS = 30
TAMPERING_GUARD_ENABLED = True
AUTO_HARDWARE_DETECTION = True

# Tampilan Debug & Visualisasi
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720
SHOW_PREVIEW = True
SHOW_ROI_BOX = True
SHOW_TRIPWIRE = True

# Database & Logging
SAVE_SNAPSHOTS = True
SNAPSHOT_DIR = "data/snapshots"
DB_PATH = "data/sessions.db"

# Cloud Database & Sync (Supabase / Managed PostgreSQL)
CLOUD_SYNC_ENABLED = os.getenv("CLOUD_SYNC_ENABLED", "False").lower() in ("true", "1")
CLOUD_DATABASE_URL = os.getenv("CLOUD_DATABASE_URL", "")  # e.g. postgresql://postgres:password@db.supabase.co:5432/postgres
CLOUD_SUPABASE_URL = os.getenv("CLOUD_SUPABASE_URL", "")  # e.g. https://xyzcompany.supabase.co
CLOUD_SUPABASE_KEY = os.getenv("CLOUD_SUPABASE_KEY", "")  # Supabase Anon/Service Key
CLOUD_SYNC_INTERVAL_SEC = 10  # Interval sinkronisasi background (detik)

LOG_DIR = "data/logs"
LOG_LEVEL = "INFO"

