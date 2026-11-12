import cv2
import numpy as np
import logging
from ultralytics import YOLO
import config
from hardware import hardware

logger = logging.getLogger(__name__)


class PureYOLOPackageDetector:
    """
    Detector MURNI berbasis Deep Learning YOLOv8 + ByteTrack.
    Sama sekali TIDAK menggunakan background subtraction (MOG2), 
    tidak menggunakan contour filtering, dan tidak menggunakan thresholding konvensional.
    Semua deteksi, bounding box, dan klasifikasi ukuran es murni dihasilkan oleh neural network YOLO.
    Terintegrasi dengan HardwareManager (GPU RTX / CPU Mini PC Adaptive).
    """

    CLASS_NAMES = {0: "es_besar", 1: "es_kecil", 2: "pekerja"}

    def __init__(self, weights_path: str = getattr(config, "YOLO_WEIGHTS_PATH", "weights/yolo_ice_best.pt"),
                 conf_thresh: float = getattr(config, "YOLO_CONF_THRESH", 0.25)):
        self.weights_path = weights_path
        self.conf_thresh = conf_thresh

        # Hardware execution profile
        self._hw_device = hardware.get_device()
        self._hw_imgsz = hardware.get_imgsz()
        self._hw_half = hardware.is_half_precision()
        self._frame_stride = hardware.hardware_info.get('recommended_stride', 1)
        self._frame_counter = 0

        logger.info(
            f"[PURE-YOLO] Memuat model neural network dari: {weights_path} | "
            f"Device: {self._hw_device} | Resolution: {self._hw_imgsz}p | FP16: {self._hw_half}"
        )
        self.model = YOLO(weights_path)

        # Counter sesi
        self.total_large = 0
        self.total_small = 0

        # Cooldown per track ID (mencegah double count untuk objek yang sama)
        self.counted_ids = set()
        self.tracker_history = {}  # {track_id: [(cx, cy), ...]}
        self.active_objects = {}   # {track_id: {'centroid': (cx, cy), 'bbox': (x, y, w, h), 'class': str}}

        self.tripwire_y = config.ROI[1] + config.TRIPWIRE_Y
        self.tripwire_flash = 0
        self.last_counted_frame = -999
        self.count_cooldown_frames = 8  # Mencegah double counting akibat ByteTrack ID-switch (< 0.8s)

        logger.info("[PURE-YOLO] Detector Deep Learning siap beroperasi.")

    @property
    def total(self):
        return self.total_large + self.total_small

    @property
    def tracker(self):
        class _TrackerCompat:
            def __init__(self, objects):
                self.objects = objects
        return _TrackerCompat(self.active_objects)

    def reset_counts(self):
        self.total_large = 0
        self.total_small = 0
        self.counted_ids.clear()
        self.tracker_history.clear()
        self.active_objects.clear()
        self.last_counted_frame = -999
        self._frame_counter = 0
        logger.info("[PURE-YOLO] Counter direset untuk sesi baru.")

    def process_frame(self, frame: np.ndarray) -> tuple:
        events = []
        if self.tripwire_flash > 0:
            self.tripwire_flash -= 1

        self._frame_counter += 1
        if self._frame_stride > 1 and self._frame_counter % self._frame_stride != 0:
            return frame, []

        fh, fw = frame.shape[:2]
        self.active_objects = {}

        # Inferensi Pure YOLO dengan tracker ByteTrack aktif + hardware acceleration
        results = self.model.track(
            frame,
            persist=True,
            conf=self.conf_thresh,
            tracker="bytetrack.yaml",
            verbose=False,
            device=self._hw_device,
            imgsz=self._hw_imgsz
        )

        active_track_ids = set()

        for r in results:
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                track_id = int(box.id[0].item()) if box.id is not None else -1

                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
                w = max(1, x2 - x1)
                h = max(1, y2 - y1)
                cx = x1 + w // 2
                cy = y1 + h // 2
                area = w * h

                cls_name = self.CLASS_NAMES.get(cls_id, "unknown")

                # Gambar Bounding Box AI
                if cls_name == "es_besar":
                    color = (0, 140, 255)  # Oranye
                    label = f"ES BESAR #{track_id} ({conf:.2f})"
                elif cls_name == "es_kecil":
                    color = (0, 230, 255)  # Kuning
                    label = f"ES KECIL #{track_id} ({conf:.2f})"
                elif cls_name == "pekerja":
                    color = (255, 120, 0)  # Biru
                    label = f"PEKERJA #{track_id} ({conf:.2f})"
                else:
                    color = (200, 200, 200)
                    label = f"Obj #{track_id} ({conf:.2f})"

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.45, 1)
                cv2.rectangle(frame, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), color, -1)
                cv2.putText(frame, label, (x1 + 2, max(th + 2, y1 - 3)),
                            cv2.FONT_HERSHEY_DUPLEX, 0.45, (0, 0, 0), 1)

                # Abaikan pekerja dari penghitungan es
                if cls_name == "pekerja" or track_id < 0:
                    continue

                active_track_ids.add(track_id)
                self.active_objects[track_id] = {
                    'centroid': (cx, cy),
                    'curr_bbox': (x1, y1, w, h),
                    'class_name': cls_name,
                    'confidence': conf,
                    'max_area': area
                }

                # Catat lintasan trajektori
                if track_id not in self.tracker_history:
                    self.tracker_history[track_id] = []
                self.tracker_history[track_id].append((cx, cy))

                # Logika Penghitungan: Arah masuk ke dalam bak truk
                # Objek es bergerak ke arah bak (cy berkurang mendekati atau melintasi batas masuk bak)
                if track_id not in self.counted_ids:
                    hist = self.tracker_history[track_id]
                    if len(hist) >= 2:
                        prev_y = hist[-2][1]
                        dy = prev_y - cy  # dy > 0 artinya bergerak ke atas/masuk truk

                        # Pengecekan garis / area masuk bak truk dengan filter gerak (dy)
                        is_crossing = (prev_y >= self.tripwire_y >= cy) or \
                                      (cy <= 1260 and dy >= 5) or \
                                      (cy <= 1220 and dy >= 3) or \
                                      (cy <= config.TRUCK_ENTRANCE_Y and 220 <= cx <= 750 and dy >= 2)

                        if is_crossing and 380 <= cx <= 740:
                            # Filter anti double-count: abaikan jika ID-switch terjadi dalam jendela cooldown
                            if (self._frame_counter - self.last_counted_frame) < self.count_cooldown_frames:
                                continue
                            self.last_counted_frame = self._frame_counter

                            # Logika Cerdas: Deteksi 2 Es Bertumpuk (Stacked Ice)
                            # Bungkusan yang benar-benar melebur/bertumpuk memiliki area raksasa >= 55.000 px
                            is_stacked = (area >= 55000)
                            qty = 2 if is_stacked else 1

                            # Penentuan ukuran hybrid: YOLO class + fallback area bungkusan
                            if is_stacked:
                                size = "large"
                                self.total_large += 2
                                logger.warning(
                                    f"🧊🧊 [STACKED ICE] 2 Es Bertumpuk #{track_id} terdeteksi "
                                    f"(Area={area}px, {w}x{h}) -> Dihitung +2!"
                                )
                            elif cls_name == "es_kecil" or area < 12000:
                                size = "small"
                                self.total_small += 1
                            else:
                                size = "large"
                                self.total_large += 1

                            self.counted_ids.add(track_id)
                            self.tripwire_flash = 8

                            crop = frame[max(0, y1):min(fh, y2), max(0, x1):min(fw, x2)].copy()
                            events.append({
                                'size': size,
                                'area': area,
                                'crop': crop,
                                'track_id': track_id,
                                'conf': conf,
                                'quantity': qty,
                                'is_stacked': is_stacked
                            })
                            logger.info(
                                f"[PURE-YOLO COUNT] {size.upper()} (x{qty}) #{track_id} terhitung | "
                                f"conf={conf:.2f} | BBox=({w}x{h}) | "
                                f"Total: Besar={self.total_large}, Kecil={self.total_small}"
                            )

        # Bersihkan history ID yang sudah tidak aktif
        if len(self.tracker_history) > 200:
            stale_ids = [tid for tid in self.tracker_history if tid not in active_track_ids]
            for tid in stale_ids[:100]:
                del self.tracker_history[tid]

        # Visualisasi Counting Line
        line_col = config.TRIPWIRE_COLOR_ACTIVE if self.tripwire_flash > 0 else config.TRIPWIRE_COLOR_IDLE
        rx, ry, rw, rh = config.ROI
        cv2.line(frame, (rx, self.tripwire_y), (rx + rw, self.tripwire_y), line_col, 2)
        cv2.putText(frame, "PURE YOLO COUNTING LINE", (rx + 5, self.tripwire_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_col, 1)

        return frame, events


# Backward-compatible alias
PackageDetector = PureYOLOPackageDetector
