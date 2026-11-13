import os
import time
import json
import logging
import threading
import requests
import sqlite3
from typing import Optional

import config
import database

logger = logging.getLogger(__name__)

class CloudSyncManager:

    def __init__(self,
                 supabase_url: str = getattr(config, "CLOUD_SUPABASE_URL", ""),
                 supabase_key: str = getattr(config, "CLOUD_SUPABASE_KEY", ""),
                 db_url: str = getattr(config, "CLOUD_DATABASE_URL", ""),
                 interval_sec: int = getattr(config, "CLOUD_SYNC_INTERVAL_SEC", 10)):
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self.db_url = db_url
        self.interval_sec = interval_sec
        self.is_enabled = getattr(config, "CLOUD_SYNC_ENABLED", False) or bool(self.supabase_url and self.supabase_key)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.last_sync_time = "Belum sinkron"
        self.sync_status = "IDLE"

        self._sync_state_file = "data/cloud_sync_state.json"
        self.state = self._load_state()

        if not self.is_enabled:
            logger.info("[CLOUD-SYNC] Cloud Database Sync dinonaktifkan (mode standalone lokal).")
        else:
            logger.info(f"[CLOUD-SYNC] Cloud Sync aktif menuju: {self.supabase_url or self.db_url}")

    def _load_state(self) -> dict:
        if os.path.exists(self._sync_state_file):
            try:
                with open(self._sync_state_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {'last_session_id': 0, 'last_package_id': 0, 'last_anomaly_id': 0}

    def _save_state(self):
        os.makedirs(os.path.dirname(self._sync_state_file), exist_ok=True)
        try:
            with open(self._sync_state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"[CLOUD-SYNC] Gagal simpan state sync: {e}")

    def start(self):
        if not self.is_enabled or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("[CLOUD-SYNC] Background sync thread dimulai.")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("[CLOUD-SYNC] Background sync thread dihentikan.")

    def _worker_loop(self):
        while self._running:
            try:
                self.sync_now()
            except Exception as e:
                logger.error(f"[CLOUD-SYNC] Error di worker loop: {e}")
                self.sync_status = "OFFLINE_RETRY"

            time.sleep(self.interval_sec)

    def sync_now(self) -> dict:
        if not self.is_enabled:
            return {'status': 'disabled', 'message': 'Cloud sync belum diaktifkan di config'}

        self.sync_status = "SYNCING"
        conn = database.get_connection()
        cur = conn.cursor()

        synced_sessions = 0
        synced_anomalies = 0

        try:

            cur.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 50")
            recent_sessions = [dict(r) for r in cur.fetchall()]
            pushed_session_ids = set()

            if recent_sessions:
                success = self._push_to_supabase("sessions", recent_sessions)
                if success:
                    synced_sessions = len(recent_sessions)
                    pushed_session_ids = {s['id'] for s in recent_sessions if s.get('id') is not None}

            cur.execute("""
                SELECT * FROM anomalies
                WHERE status IN ('CONFIRMED_THEFT', 'POWER_RESTORED', 'RESOLVED')
                   OR anomaly_type LIKE 'CAMERA_%'
                   OR anomaly_type LIKE 'POWER_%'
                   OR anomaly_type LIKE 'SYSTEM_%'
                ORDER BY id DESC LIMIT 50
            """)
            recent_anomalies = [dict(r) for r in cur.fetchall()]

            if recent_anomalies:
                needed_ids = {
                    a['session_id'] for a in recent_anomalies
                    if a.get('session_id') is not None and a['session_id'] not in pushed_session_ids
                }
                existing_ids = set(pushed_session_ids)
                if needed_ids:
                    placeholders = ",".join("?" for _ in needed_ids)
                    cur.execute(f"SELECT * FROM sessions WHERE id IN ({placeholders})", tuple(needed_ids))
                    extra_sessions = [dict(r) for r in cur.fetchall()]
                    if extra_sessions and self._push_to_supabase("sessions", extra_sessions):
                        existing_ids.update(s['id'] for s in extra_sessions if s.get('id') is not None)

                for a in recent_anomalies:
                    if a.get('session_id') not in existing_ids:
                        a['session_id'] = None

                success = self._push_to_supabase("anomalies", recent_anomalies)
                if success:
                    synced_anomalies = len(recent_anomalies)

            self._save_state()
            self.last_sync_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self.sync_status = "SUCCESS"
            return {
                'status': 'success',
                'synced_sessions': synced_sessions,
                'synced_anomalies': synced_anomalies,
                'last_sync_time': self.last_sync_time
            }

        except requests.exceptions.ConnectionError:
            self.sync_status = "OFFLINE_RETRY"
            logger.warning("[CLOUD-SYNC] Koneksi internet pabrik terputus. Data diantrekan di SQLite lokal.")
            return {'status': 'offline', 'message': 'Internet offline. Data aman di lokal SQLite.'}
        except Exception as e:
            self.sync_status = "ERROR"
            logger.error(f"[CLOUD-SYNC] Gagal sinkronisasi data: {e}")
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    def _push_to_supabase(self, table_name: str, records: list) -> bool:
        if not self.supabase_url or not self.supabase_key:
            return False

        url = f"{self.supabase_url}/rest/v1/{table_name}"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

        resp = requests.post(url, headers=headers, json=records, timeout=10)
        if resp.status_code in (200, 201):
            logger.info(f"[CLOUD-SYNC] Berhasil sync {len(records)} baris ke Supabase table: {table_name}")
            return True
        else:
            logger.error(f"[CLOUD-SYNC] Supabase error ({resp.status_code}): {resp.text}")
            return False

cloud_sync = CloudSyncManager()
