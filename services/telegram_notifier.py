import os
import time
import logging
import threading
import requests
from collections import deque
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLE_ALERTS

logger = logging.getLogger(__name__)

class TelegramNotifier:

    def __init__(self, token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.enabled = TELEGRAM_ENABLE_ALERTS and bool(token and chat_id)
        self._offline_queue: deque = deque(maxlen=50)
        self._lock = threading.Lock()

        if not self.enabled:
            logger.info(
                "[TELEGRAM] Token atau Chat ID belum diset. "
                "Notifikasi Telegram dinonaktifkan (mode simulasi/lokal)."
            )

    def send_alert_async(self, title: str, details: dict, video_path: str = None, on_success=None):
        threading.Thread(
            target=self._send_with_retry,
            args=(title, details, video_path, on_success),
            daemon=True
        ).start()

    def _send_with_retry(self, title: str, details: dict, video_path: str = None, on_success=None):
        success = self.send_alert(title, details, video_path, on_success)
        if not success and self.enabled:
            logger.warning("[TELEGRAM] Gagal kirim alert. Memasukkan ke antrean offline...")
            with self._lock:
                self._offline_queue.append({
                    'title': title,
                    'details': details,
                    'video_path': video_path,
                    'queued_at': time.strftime("%H:%M:%S"),
                    'on_success': on_success
                })

    def flush_offline_queue(self):
        if not self.enabled or len(self._offline_queue) == 0:
            return

        with self._lock:
            pending = list(self._offline_queue)
            self._offline_queue.clear()

        logger.info(f"[TELEGRAM] Memulai flush {len(pending)} alert offline...")
        for item in pending:
            success = self.send_alert(
                item['title'], item['details'],
                item.get('video_path'), item.get('on_success')
            )
            if not success:

                with self._lock:
                    self._offline_queue.append(item)
                break
            time.sleep(0.5)

    def send_alert(self, title: str, details: dict, video_path: str = None, on_success=None) -> bool:
        if not self.enabled:
            logger.info(
                f"[TELEGRAM SIMULASI] Alert '{title}' dipicu untuk Truk {details.get('truck_id', '-')}. "
                f"Video: {video_path}"
            )
            return False

        message = (
            f"🚨 *{title}* 🚨\n\n"
            f"📍 *Kota*: {details.get('city', 'Makassar')}\n"
            f"🚛 *Nomor Truk*: #{details.get('truck_id', '-')}\n"
            f"🔢 *Trip ke-*: #{details.get('trip_number', 1)}\n"
            f"⏰ *Waktu*: {details.get('timestamp', '-')}\n"
            f"⚠️ *Keterangan*: {details.get('message', 'Terdeteksi gerakan mencurigakan')}\n"
        )

        success = False
        try:
            text_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = requests.post(text_url, json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }, timeout=10)

            if resp.status_code == 200:
                success = True
                logger.info("[TELEGRAM] Notifikasi teks terkirim.")
            else:
                logger.error(f"[TELEGRAM] Gagal kirim teks: {resp.text}")

            if video_path and os.path.exists(video_path) and success:
                video_url = f"https://api.telegram.org/bot{self.token}/sendVideo"
                with open(video_path, 'rb') as vf:
                    v_resp = requests.post(video_url, data={
                        'chat_id': self.chat_id,
                        'caption': f"🎥 Bukti Video: Truk #{details.get('truck_id', '-')}"
                    }, files={'video': vf}, timeout=30)
                    if v_resp.status_code == 200:
                        logger.info(f"[TELEGRAM] Video bukti terkirim: {video_path}")
                    else:
                        logger.error(f"[TELEGRAM] Gagal kirim video: {v_resp.text}")

            if success and on_success:
                on_success()

        except requests.exceptions.ConnectionError:
            logger.warning("[TELEGRAM] Koneksi internet terputus. Alert akan dikantrekan.")
            return False
        except Exception as e:
            logger.error(f"[TELEGRAM] Kesalahan saat mengirim notifikasi: {e}")
            return False

        return success
