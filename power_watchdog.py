import os
import time
import json
import logging
import threading
from datetime import datetime
from typing import Optional

import config
import database
from telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class PowerWatchdog:
    """
    SOTA Industrial Edge Power-Loss & Outage Watchdog:
    1. Menyimpan heartbeat state setiap 2 detik ke disk secara persisten.
    2. Mendeteksi mati listrik mendadak (sudden blackout / power failure) saat PC booting kembali.
    3. Menghitung durasi pemadaman listrik (downtime duration) secara presisi.
    4. Mencatat insiden ke SQLite lokal + Cloud Supabase PostgreSQL.
    5. Mengirimkan notifikasi darurat Telegram langsung ke pimpinan saat listrik pulih.
    """

    STATE_FILE = "data/power_state.json"

    def __init__(self,
                 city: str = getattr(config, "DEFAULT_CITY", "Makassar"),
                 branch_code: str = getattr(config, "BRANCH_CODE", "MKS-01"),
                 telegram: Optional[TelegramNotifier] = None):
        self.city = city
        self.branch_code = branch_code
        self.telegram = telegram or TelegramNotifier()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def check_recovery_on_boot(self, cloud_sync_mgr=None) -> Optional[dict]:
        """
        Dijalankan saat sistem mulai menyala (boot / app startup).
        Mengecek apakah sesi sebelumnya dihentikan secara normal atau karena MATI LAMPU MENDADAK.
        """
        if not os.path.exists(self.STATE_FILE):
            self._save_state(clean_shutdown=False)
            return None

        try:
            with open(self.STATE_FILE, "r") as f:
                prev_state = json.load(f)
        except Exception as e:
            logger.error(f"[POWER-GUARD] Gagal membaca state power: {e}")
            self._save_state(clean_shutdown=False)
            return None

        clean_shutdown = prev_state.get("clean_shutdown", True)
        last_heartbeat = prev_state.get("last_heartbeat_timestamp", 0)
        last_heartbeat_iso = prev_state.get("last_heartbeat_iso", "Tidak diketahui")
        now_ts = time.time()
        downtime_sec = int(now_ts - last_heartbeat)

        outage_info = None

        # Jika sebelumnya tidak clean_shutdown dan jeda waktu > 10 detik -> MATI LISTRIK!
        if not clean_shutdown and downtime_sec > 10:
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            minutes = downtime_sec // 60
            seconds = downtime_sec % 60
            durasi_str = f"{minutes} menit {seconds} detik" if minutes > 0 else f"{seconds} detik"

            logger.critical(
                f"⚡ [MATI LISTRIK MENDADAK TERDETEKSI] Pabrik mati sejak {last_heartbeat_iso} "
                f"s/d {now_iso} (Total padam: {durasi_str})."
            )

            # 1. Catat ke Database
            detail_msg = (
                f"⚡ Mati listrik mendadak terdeteksi! Sistem padam sejak {last_heartbeat_iso} "
                f"s/d {now_iso} (Durasi padam: {durasi_str}). "
                f"Sistem telah pulih otomatis dan monitoring CCTV aktif kembali."
            )
            anom_id = database.log_anomaly(
                session_id=None,
                frame_idx=0,
                anomaly_type="POWER_OUTAGE_SUDDEN",
                status="POWER_RESTORED",
                details=detail_msg,
                city=self.city,
                branch_code=self.branch_code
            )

            # 2. Trigger Notifikasi Darurat Telegram
            alert_details = {
                'city': self.city,
                'branch_code': self.branch_code,
                'timestamp': now_iso,
                'outage_start': last_heartbeat_iso,
                'outage_restored': now_iso,
                'downtime': durasi_str,
                'status': 'LISTRIK PULIH (SISTEM RECOVERED)',
                'message': (
                    f"⚠️ PERINGATAN LISTRIK PADAM PABRIK:\n"
                    f"Terdeteksi pemadaman listrik mendadak di cabang {self.city} ({self.branch_code}).\n\n"
                    f"• Waktu Padam : {last_heartbeat_iso}\n"
                    f"• Waktu Nyala : {now_iso}\n"
                    f"• Durasi Mati : {durasi_str}\n\n"
                    f"✅ Sistem AI CCTV & Mini PC telah otomatis menyala kembali (Auto-Recovery)."
                )
            }
            self.telegram.send_alert_async(
                title="⚡ LAPORAN PEMULIHAN MATI LISTRIK PABRIK",
                details=alert_details
            )

            # 3. Segera sinkronkan ke Supabase Cloud
            if cloud_sync_mgr:
                cloud_sync_mgr.sync_now()

            outage_info = {
                'anomaly_id': anom_id,
                'outage_start': last_heartbeat_iso,
                'outage_restored': now_iso,
                'downtime_sec': downtime_sec,
                'downtime_str': durasi_str
            }

        # Reset state untuk sesi baru yang sedang berjalan saat ini
        self._save_state(clean_shutdown=False)
        return outage_info

    def start_heartbeat(self):
        """Mulai background heartbeat thread setiap 2 detik."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("[POWER-GUARD] Power Watchdog heartbeat thread aktif.")

    def stop_heartbeat(self, clean_shutdown: bool = True):
        """Hentikan heartbeat dan tandai shutdown normal."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._save_state(clean_shutdown=clean_shutdown)
        logger.info(f"[POWER-GUARD] Power Watchdog dihentikan (clean_shutdown={clean_shutdown}).")

    def _heartbeat_loop(self):
        while self._running:
            self._save_state(clean_shutdown=False)
            time.sleep(2.0)

    def _save_state(self, clean_shutdown: bool = False):
        os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
        data = {
            'last_heartbeat_timestamp': time.time(),
            'last_heartbeat_iso': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'clean_shutdown': clean_shutdown,
            'branch_code': self.branch_code,
            'city': self.city
        }
        try:
            with open(self.STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[POWER-GUARD] Gagal update heartbeat state: {e}")

    def simulate_power_outage(self, downtime_minutes: int = 15, cloud_sync_mgr=None) -> dict:
        """
        Simulasi uji coba mati listrik untuk testing operasional & demo manajemen.
        """
        now = datetime.now()
        now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
        past_ts = time.time() - (downtime_minutes * 60)
        past_iso = datetime.fromtimestamp(past_ts).strftime("%Y-%m-%d %H:%M:%S")
        durasi_str = f"{downtime_minutes} menit 0 detik"

        detail_msg = (
            f"⚡ [SIMULASI] Terdeteksi mati listrik mendadak di pabrik! "
            f"Sistem padam sejak {past_iso} s/d {now_iso} (Durasi padam: {durasi_str}). "
            f"Sistem telah pulih otomatis dan monitoring CCTV aktif kembali."
        )

        anom_id = database.log_anomaly(
            session_id=None,
            frame_idx=0,
            anomaly_type="POWER_OUTAGE_SUDDEN",
            status="POWER_RESTORED",
            details=detail_msg,
            city=self.city,
            branch_code=self.branch_code
        )

        alert_details = {
            'city': self.city,
            'branch_code': self.branch_code,
            'timestamp': now_iso,
            'outage_start': past_iso,
            'outage_restored': now_iso,
            'downtime': durasi_str,
            'status': 'LISTRIK PULIH (SIMULASI RECOVERED)',
            'message': (
                f"⚡ SIMULASI LAPORAN LISTRIK PADAM PABRIK:\n"
                f"Terdeteksi pemadaman listrik di cabang {self.city} ({self.branch_code}).\n\n"
                f"• Waktu Padam : {past_iso}\n"
                f"• Waktu Nyala : {now_iso}\n"
                f"• Durasi Mati : {durasi_str}\n\n"
                f"✅ Sistem AI CCTV & Mini PC otomatis pulih dan melanjutkan pengawasan."
            )
        }

        self.telegram.send_alert_async(
            title="⚡ SIMULASI: LAPORAN LISTRIK PADAM PABRIK",
            details=alert_details
        )

        if cloud_sync_mgr:
            cloud_sync_mgr.sync_now()

        return {
            'status': 'success',
            'anomaly_id': anom_id,
            'outage_start': past_iso,
            'outage_restored': now_iso,
            'downtime': durasi_str,
            'details': detail_msg
        }


power_watchdog = PowerWatchdog()
