import cv2
import time
import threading
import logging
import numpy as np

logger = logging.getLogger(__name__)


class RTSPStreamManager:
    """
    SOTA Resilient RTSP Stream Manager:
    1. Zero-Lag Frame Grabber: background thread mengambil frame terbaru, mencegah buffer lag.
    2. Auto-Reconnect Loop: menyambung ulang otomatis jika RTSP terputus tanpa membuat aplikasi crash.
    3. Camera Tampering Guard: mendeteksi jika kamera ditutup kain (gelap), disorot senter (silau ekstrim),
       atau video membeku (frozen video attack).
    """

    def __init__(self, source: str, fps_target: float = 10.0,
                 on_tampering=None, on_disconnect=None, on_reconnect=None):
        self.source = source
        self.fps_target = fps_target
        self.on_tampering = on_tampering
        self.on_disconnect = on_disconnect
        self.on_reconnect = on_reconnect

        self._cap = None
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Buffer 1 frame terbaru (Zero-Lag)
        self._latest_frame = None
        self._frame_idx = 0
        self._last_frame_time = 0

        # State koneksi & tampering
        self.is_connected = False
        self.tamper_status = "NORMAL"  # NORMAL, BLACKOUT, BLINDED, FROZEN
        self._frozen_frame_count = 0
        self._prev_tamper_frame = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_worker, daemon=True)
        self._thread.start()
        logger.info(f"[STREAM] Stream Manager dimulai untuk sumber: {self.source}")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._release_cap()
        logger.info("[STREAM] Stream Manager dihentikan.")

    def get_latest_frame(self) -> tuple:
        """
        Mengambil frame terbaru secara non-blocking dengan zero-latency.
        Mengembalikan: (success: bool, frame: np.ndarray, frame_idx: int)
        """
        with self._lock:
            if self._latest_frame is None:
                return False, None, 0
            return True, self._latest_frame.copy(), self._frame_idx

    def _release_cap(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _open_stream(self) -> bool:
        self._release_cap()
        logger.info(f"[STREAM] Menghubungkan ke sumber stream: {self.source}...")

        is_rtsp = str(self.source).lower().startswith("rtsp://") or str(self.source).lower().startswith("http://")

        # Inisialisasi VideoCapture dengan buffer size = 1 untuk mencegah lag
        cap = cv2.VideoCapture(self.source)
        if is_rtsp:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if cap.isOpened():
            self._cap = cap
            self.is_connected = True
            logger.info("[STREAM] Koneksi stream BERHASIL dibuat.")
            if self.on_reconnect:
                self.on_reconnect()
            return True
        else:
            self.is_connected = False
            logger.warning("[STREAM] Gagal membuka stream. Memasuki antrean reconnect...")
            return False

    def _capture_worker(self):
        reconnect_delay = 2.0
        max_reconnect_delay = 15.0

        while self._running:
            # 1. Pastikan koneksi stream terbuka
            if self._cap is None or not self._cap.isOpened():
                success = self._open_stream()
                if not success:
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(max_reconnect_delay, reconnect_delay * 1.5)
                    continue
                else:
                    reconnect_delay = 2.0

            # 2. Baca frame dari stream
            ret, frame = self._cap.read()
            now = time.time()

            if not ret or frame is None:
                logger.warning("[STREAM] Gagal membaca frame / stream terputus!")
                self.is_connected = False
                if self.on_disconnect:
                    self.on_disconnect()
                self._release_cap()
                time.sleep(reconnect_delay)
                continue

            # 3. Jalankan pemeriksaan Camera Tampering Guard
            self._check_camera_tampering(frame)

            # 4. Simpan frame terbaru ke slot memori dengan zero-lag
            with self._lock:
                self._latest_frame = frame
                self._frame_idx += 1
                self._last_frame_time = now

            # Jika membaca file video offline (bukan RTSP live), beri jeda waktu sesuai FPS
            if not str(self.source).lower().startswith("rtsp://"):
                time.sleep(1.0 / self.fps_target)

    def _check_camera_tampering(self, frame: np.ndarray):
        """
        Deteksi sabotase kamera:
        - BLACKOUT: kamera ditutup kain/cat (mean brightness < 12)
        - BLINDED: kamera disorot laser/senter sangat terang (mean brightness > 245)
        - FROZEN: video membeku karena sabotase feed kamera
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(gray.mean())

        current_tamper = "NORMAL"

        if mean_brightness < 12.0:
            current_tamper = "TAMPER_BLACKOUT"
        elif mean_brightness > 246.0:
            current_tamper = "TAMPER_BLINDED"
        else:
            # Cek freeze video
            if self._prev_tamper_frame is not None:
                diff = cv2.absdiff(self._prev_tamper_frame, gray)
                diff_sum = float(diff.sum() / (gray.shape[0] * gray.shape[1]))
                if diff_sum < 0.3:  # Gambar identik persis
                    self._frozen_frame_count += 1
                    if self._frozen_frame_count >= 40:  # ~4 detik membeku
                        current_tamper = "TAMPER_FROZEN"
                else:
                    self._frozen_frame_count = 0
            self._prev_tamper_frame = gray

        if current_tamper != "NORMAL" and current_tamper != self.tamper_status:
            self.tamper_status = current_tamper
            logger.error(f"🚨 [SABOTASE KAMERA TERDETEKSI]: {current_tamper} (Brightness={mean_brightness:.1f})")
            if self.on_tampering:
                self.on_tampering(current_tamper, mean_brightness)
        elif current_tamper == "NORMAL" and self.tamper_status != "NORMAL":
            logger.info("[STREAM] Kamera kembali normal dari status sabotase.")
            self.tamper_status = "NORMAL"

