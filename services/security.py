import os
import re
import hmac
import hashlib
import secrets
import time
import glob
import threading
import logging
from urllib.parse import urlparse
import ipaddress
import psutil
from datetime import datetime, timedelta
from fastapi import Header, HTTPException, Request, Security
import config

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "es_session"
ALLOWED_VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov")

class SecurityStorageManager:

    def __init__(self, evidence_dir: str = None,
                 max_disk_usage_pct: float = None,
                 retention_days: int = None,
                 snapshot_dir: str = None,
                 snapshot_retention_days: int = None):
        self._evidence_dir = evidence_dir
        self._snapshot_dir = snapshot_dir
        self._max_disk_usage_pct = max_disk_usage_pct
        self._retention_days = retention_days
        self._snapshot_retention_days = snapshot_retention_days
        os.makedirs(self.evidence_dir, exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)

    @property
    def evidence_dir(self) -> str:
        return self._evidence_dir or getattr(config, "EVIDENCE_DIR", "data/evidence")

    @evidence_dir.setter
    def evidence_dir(self, value: str):
        self._evidence_dir = value

    @property
    def snapshot_dir(self) -> str:
        return self._snapshot_dir or getattr(config, "SNAPSHOT_DIR", "data/snapshots")

    @property
    def max_disk_usage_pct(self) -> float:
        if self._max_disk_usage_pct is not None:
            return self._max_disk_usage_pct
        return float(getattr(config, "MAX_DISK_USAGE_PERCENT", 85.0))

    @property
    def retention_days(self) -> int:
        if self._retention_days is not None:
            return self._retention_days
        return int(getattr(config, "EVIDENCE_RETENTION_DAYS", 30))

    @property
    def snapshot_retention_days(self) -> int:
        if self._snapshot_retention_days is not None:
            return self._snapshot_retention_days
        return int(getattr(config, "SNAPSHOT_RETENTION_DAYS", 7))

    @staticmethod
    def compute_file_sha256(filepath: str) -> str:
        if not os.path.exists(filepath):
            return ""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _prune_old_files(self, directory: str, patterns: tuple, days: int) -> tuple[int, int]:
        if days <= 0 or not os.path.isdir(directory):
            return 0, 0
        cutoff = time.time() - (days * 86400)
        count = 0
        freed = 0
        for pat in patterns:
            for f in glob.glob(os.path.join(directory, pat)):
                try:
                    if os.path.getmtime(f) < cutoff:
                        sz = os.path.getsize(f)
                        os.remove(f)
                        count += 1
                        freed += sz
                except Exception as e:
                    logger.error(f"[STORAGE] Gagal hapus file kedaluwarsa {f}: {e}")
        return count, freed

    def check_and_prune_disk(self) -> dict:
        os.makedirs(self.evidence_dir, exist_ok=True)
        expired_count, expired_bytes = self._prune_old_files(
            self.evidence_dir, ("*.mp4", "*.avi"), self.retention_days
        )
        snap_count, snap_bytes = self._prune_old_files(
            self.snapshot_dir, ("*.jpg", "*.jpeg", "*.png"), self.snapshot_retention_days
        )

        disk = psutil.disk_usage(self.evidence_dir)
        total_gb = round(disk.total / (1024 ** 3), 1)
        free_gb = round(disk.free / (1024 ** 3), 1)
        used_percent = disk.percent

        pruned_count = expired_count
        pruned_bytes = expired_bytes + snap_bytes

        if used_percent >= self.max_disk_usage_pct:
            logger.warning(
                f"[STORAGE] Pemakaian disk mencapai {used_percent}%! "
                f"Memulai pembersihan otomatis (Auto-Prune)..."
            )
            files = sorted(
                glob.glob(os.path.join(self.evidence_dir, "*.mp4")) + glob.glob(os.path.join(self.evidence_dir, "*.avi")),
                key=os.path.getmtime
            )
            for f in files:
                try:
                    f_size = os.path.getsize(f)
                    os.remove(f)
                    pruned_count += 1
                    pruned_bytes += f_size

                    cur_disk = psutil.disk_usage(self.evidence_dir)
                    if cur_disk.percent < (self.max_disk_usage_pct - 5.0):
                        break
                except Exception as e:
                    logger.error(f"[STORAGE] Gagal menghapus file lama {f}: {e}")

            disk = psutil.disk_usage(self.evidence_dir)
            free_gb = round(disk.free / (1024 ** 3), 1)
            used_percent = disk.percent

        return {
            'total_gb': total_gb,
            'free_gb': free_gb,
            'used_percent': used_percent,
            'pruned_files_count': pruned_count,
            'pruned_expired_count': expired_count,
            'pruned_snapshots_count': snap_count,
            'pruned_mb': round(pruned_bytes / (1024 ** 2), 1),
            'retention_days': self.retention_days,
            'snapshot_retention_days': self.snapshot_retention_days
        }

security_manager = SecurityStorageManager()

def verify_api_key(x_api_key: str = Header(default="")):
    if not getattr(config, "REQUIRE_API_KEY", True):
        return True
    secret = getattr(config, "API_SECRET_KEY", "")
    if not secret:
        raise HTTPException(status_code=503, detail="API_SECRET_KEY belum dikonfigurasi di .env")
    if not hmac.compare_digest(x_api_key.encode(), secret.encode()):
        raise HTTPException(status_code=403, detail="Akses ditolak: API Key tidak valid.")
    return True

def hash_password(password: str, salt_hex: str = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    if not password or not stored:
        return False
    if stored.startswith("scrypt$"):
        parts = stored.split("$")
        if len(parts) != 3:
            return False
        try:
            salt = bytes.fromhex(parts[1])
            expected = bytes.fromhex(parts[2])
        except ValueError:
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    d1 = hashlib.sha256(password.encode("utf-8")).digest()
    d2 = hashlib.sha256(stored.encode("utf-8")).digest()
    return hmac.compare_digest(d1, d2)

def _resolve_role_accounts() -> list:
    accounts = []
    admin_secret = getattr(config, "ADMIN_PASSWORD_HASH", "") or getattr(config, "ADMIN_PASSWORD", "") or getattr(config, "API_SECRET_KEY", "")
    if admin_secret:
        accounts.append((getattr(config, "ADMIN_USERNAME", "admin"), admin_secret, "admin"))
    op_secret = getattr(config, "OPERATOR_PASSWORD_HASH", "") or getattr(config, "OPERATOR_PASSWORD", "")
    if op_secret:
        accounts.append((getattr(config, "OPERATOR_USERNAME", "operator"), op_secret, "operator"))
    return accounts

def is_auth_configured() -> bool:
    return len(_resolve_role_accounts()) > 0

def authenticate_user(username: str, password: str) -> dict | None:
    user_clean = (username or "").strip()
    accounts = _resolve_role_accounts()
    matched = None
    for acct_user, acct_secret, acct_role in accounts:
        user_ok = hmac.compare_digest(user_clean.lower().encode("utf-8"), acct_user.lower().encode("utf-8"))
        pass_ok = verify_password(password, acct_secret)
        if user_ok and pass_ok and matched is None:
            matched = {"username": acct_user, "role": acct_role}
    return matched

class LoginRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._records = {}

    def _prune_locked(self, now: float):
        if len(self._records) <= 2048:
            return
        cutoff = now - max(60, int(getattr(config, "LOGIN_LOCKOUT_SECONDS", 300)))
        stale = [ip for ip, rec in self._records.items() if rec["locked_until"] < now and (not rec["fails"] or rec["fails"][-1] < cutoff)]
        for ip in stale[:1024]:
            del self._records[ip]

    def check_locked(self, ip: str) -> int:
        now = time.time()
        with self._lock:
            rec = self._records.get(ip)
            if not rec:
                return 0
            rem = int(rec["locked_until"] - now)
            return rem if rem > 0 else 0

    def record_failure(self, ip: str) -> int:
        now = time.time()
        window = max(60, int(getattr(config, "LOGIN_LOCKOUT_SECONDS", 300)))
        max_attempts = max(2, int(getattr(config, "LOGIN_MAX_ATTEMPTS", 5)))
        with self._lock:
            self._prune_locked(now)
            rec = self._records.setdefault(ip, {"fails": [], "locked_until": 0.0})
            rec["fails"] = [t for t in rec["fails"] if now - t <= window]
            rec["fails"].append(now)
            if len(rec["fails"]) >= max_attempts:
                rec["locked_until"] = now + window
                rec["fails"].clear()
                return window
            return 0

    def reset(self, ip: str):
        with self._lock:
            self._records.pop(ip, None)

class SessionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    def _is_expired(self, s: dict, now: float) -> bool:
        ttl = max(60, int(getattr(config, "SESSION_TTL_MINUTES", 480)) * 60)
        idle = max(60, int(getattr(config, "SESSION_IDLE_MINUTES", 60)) * 60)
        return (now - s["created_at"] > ttl) or (now - s["last_seen"] > idle)

    def create_session(self, username: str, role: str, ip: str) -> dict:
        now = time.time()
        sid = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        data = {
            "sid": sid,
            "username": username,
            "role": role,
            "csrf_token": csrf_token,
            "created_at": now,
            "last_seen": now,
            "ip": ip,
        }
        with self._lock:
            expired = [k for k, v in self._sessions.items() if self._is_expired(v, now)]
            for k in expired:
                del self._sessions[k]
            if len(self._sessions) >= 500:
                oldest = sorted(self._sessions.items(), key=lambda item: item[1]["last_seen"])[:100]
                for k, _ in oldest:
                    del self._sessions[k]
            self._sessions[sid] = data
        return dict(data)

    def get_session(self, sid: str, touch: bool = True) -> dict | None:
        if not sid:
            return None
        now = time.time()
        with self._lock:
            s = self._sessions.get(sid)
            if not s:
                return None
            if self._is_expired(s, now):
                del self._sessions[sid]
                return None
            if touch:
                s["last_seen"] = now
            return dict(s)

    def revoke_session(self, sid: str) -> dict | None:
        if not sid:
            return None
        with self._lock:
            return self._sessions.pop(sid, None)

    def clear_all(self):
        with self._lock:
            self._sessions.clear()

login_rate_limiter = LoginRateLimiter()
session_manager = SessionManager()

def get_session_from_cookies(cookies: dict, touch: bool = True) -> dict | None:
    sid = cookies.get(SESSION_COOKIE_NAME, "") if cookies else ""
    return session_manager.get_session(sid, touch=touch)

def require_session(request: Request) -> dict:
    sess = session_manager.get_session(request.cookies.get(SESSION_COOKIE_NAME, ""), touch=True)
    if not sess:
        raise HTTPException(status_code=401, detail="Silakan masuk terlebih dahulu.")
    return sess

def verify_csrf(request: Request, session: dict):
    token = request.headers.get("X-CSRF-Token", "")
    if not token or not hmac.compare_digest(token.encode("utf-8"), session["csrf_token"].encode("utf-8")):
        raise HTTPException(status_code=403, detail="Token keamanan halaman (CSRF) tidak valid.")
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if origin:
        parsed = urlparse(origin)
        host_header = request.headers.get("Host", "")
        if parsed.netloc and host_header and parsed.netloc.lower() != host_header.lower():
            allowed = {urlparse(o).netloc.lower() for o in getattr(config, "CORS_ORIGINS", [])}
            if parsed.netloc.lower() not in allowed:
                raise HTTPException(status_code=403, detail="Permintaan lintas situs ditolak.")

def require_admin_csrf(request: Request, x_api_key: str = Header(default="")) -> dict:
    if x_api_key:
        verify_api_key(x_api_key)
        return {"username": "api_key", "role": "admin", "sid": ""}
    sess = require_session(request)
    if sess.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya Admin yang boleh melakukan aksi ini.")
    verify_csrf(request, sess)
    return sess

def mask_rtsp_url(source: str) -> str:
    if not source:
        return ""
    return re.sub(r"^([a-zA-Z0-9+.-]+://)([^/@]+@)", r"\1***@", str(source))

def _resolve_under_root(path_str: str) -> str:
    base = os.path.realpath(getattr(config, "ROOT_DIR", os.getcwd()))
    p = os.path.expanduser(path_str)
    if not os.path.isabs(p):
        p = os.path.join(base, p)
    return os.path.realpath(p)

def validate_video_source(source: str, videos_dir: str = "videos") -> str:
    raw = (source or "").strip()
    if not raw or len(raw) > 512 or any(c in raw for c in ("\x00", "\r", "\n")):
        raise ValueError("Sumber video tidak valid.")
    lower = raw.lower()
    if "://" in lower:
        parsed = urlparse(raw)
        if parsed.scheme.lower() not in ("rtsp", "rtsps"):
            raise ValueError("Hanya protokol rtsp:// atau file di folder videos/ yang diizinkan.")
        host = parsed.hostname
        if not host:
            raise ValueError("Alamat kamera RTSP tidak valid.")
        h_low = host.lower()
        if h_low in ("localhost", "ip6-localhost") or h_low.endswith(".local"):
            raise ValueError("Alamat kamera lokal loopback tidak diizinkan.")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
                raise ValueError("Alamat IP kamera tidak diizinkan.")
        except ValueError as err:
            if "tidak diizinkan" in str(err):
                raise
        return raw
    root_videos = _resolve_under_root(videos_dir)
    candidate = os.path.realpath(os.path.join(_resolve_under_root("."), raw) if not os.path.isabs(raw) else raw)
    try:
        common = os.path.commonpath([candidate, root_videos])
    except ValueError:
        raise ValueError("Lokasi file video harus berada di dalam folder videos/.")
    if common != root_videos:
        raise ValueError("Lokasi file video harus berada di dalam folder videos/.")
    if os.path.splitext(candidate)[1].lower() not in ALLOWED_VIDEO_EXTS:
        raise ValueError("Format file video tidak didukung.")
    if not os.path.isfile(candidate):
        raise ValueError("File video tidak ditemukan di folder videos/.")
    return candidate

def resolve_safe_file(directory: str, filename: str, allowed_exts: tuple) -> str:
    if not filename or "/" in filename or "\\" in filename or os.path.basename(filename) != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")
    if os.path.splitext(filename)[1].lower() not in allowed_exts:
        raise HTTPException(status_code=400, detail="Tipe file tidak diizinkan.")
    base_dir = _resolve_under_root(directory)
    target = os.path.realpath(os.path.join(base_dir, filename))
    try:
        if os.path.commonpath([target, base_dir]) != base_dir:
            raise HTTPException(status_code=403, detail="Akses file ditolak.")
    except ValueError:
        raise HTTPException(status_code=403, detail="Akses file ditolak.")
    return target

def sanitize_csv_cell(value) -> str:
    s = "" if value is None else str(value).replace("\r", " ").replace("\n", " ")
    if s and (s[0] in ("=", "+", "-", "@", "\t") or s.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + s
    return s
