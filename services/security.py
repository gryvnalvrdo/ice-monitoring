import os
import hmac
import hashlib
import time
import glob
import logging
import psutil
from datetime import datetime, timedelta
from fastapi import Header, HTTPException, Security
import config

logger = logging.getLogger(__name__)

class SecurityStorageManager:

    def __init__(self, evidence_dir: str = config.EVIDENCE_DIR,
                 max_disk_usage_pct: float = 85.0,
                 retention_days: int = 30):
        self.evidence_dir = evidence_dir
        self.max_disk_usage_pct = max_disk_usage_pct
        self.retention_days = retention_days
        os.makedirs(self.evidence_dir, exist_ok=True)

    @staticmethod
    def compute_file_sha256(filepath: str) -> str:
        if not os.path.exists(filepath):
            return ""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def check_and_prune_disk(self) -> dict:
        disk = psutil.disk_usage(self.evidence_dir)
        total_gb = round(disk.total / (1024 ** 3), 1)
        free_gb = round(disk.free / (1024 ** 3), 1)
        used_percent = disk.percent

        pruned_count = 0
        pruned_bytes = 0

        if used_percent >= self.max_disk_usage_pct:
            logger.warning(
                f"[STORAGE] Pemakaian disk mencapai {used_percent}%! "
                f"Memulai pembersihan otomatis (Auto-Prune)..."
            )
            files = sorted(
                glob.glob(os.path.join(self.evidence_dir, "*.mp4")),
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

        return {
            'total_gb': total_gb,
            'free_gb': free_gb,
            'used_percent': used_percent,
            'pruned_files_count': pruned_count,
            'pruned_mb': round(pruned_bytes / (1024 ** 2), 1)
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
