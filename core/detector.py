import cv2
import numpy as np
import logging
from ultralytics import YOLO
import config
from hardware import hardware

logger = logging.getLogger(__name__)

class PureYOLOPackageDetector:

    CLASS_NAMES = {0: "es_besar", 1: "es_kecil", 2: "pekerja"}

    def __init__(self, weights_path: str = getattr(config, "YOLO_WEIGHTS_PATH", "weights/yolo_ice_best.pt"),
                 conf_thresh: float = getattr(config, "YOLO_CONF_THRESH", 0.25)):
        self.weights_path = weights_path
        self.conf_thresh = conf_thresh

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

        self.total_large = 0
        self.total_small = 0

        self.counted_ids = set()
        self.counted_at_frame = {}
        self.tracker_history = {}
        self.last_seen_frame = {}
        self.active_objects = {}
        self.track_trajectories = {}

        self.tripwire_flash = 0
        self.last_counted_frame = -999
        self.count_cooldown_frames = 8

        logger.info("[PURE-YOLO] Detector Deep Learning siap beroperasi.")

    @property
    def tripwire_y(self):
        return config.ROI[1] + config.TRIPWIRE_Y

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
        self.counted_at_frame.clear()
        self.tracker_history.clear()
        self.last_seen_frame.clear()
        self.active_objects.clear()
        if hasattr(self, "track_trajectories"):
            self.track_trajectories.clear()
        self.last_counted_frame = -999
        self._frame_counter = 0
        logger.info("[PURE-YOLO] Counter direset untuk sesi baru.")

    def _record_and_should_count(self, track_id: int, cx: int, cy: int) -> bool:
        is_new_track = track_id not in self.tracker_history
        if is_new_track:
            self.tracker_history[track_id] = []
        elif track_id in self.counted_ids:
            cnt_frame, min_y_since_cnt = self.counted_at_frame.get(track_id, (-999, cy))
            min_y_since_cnt = min(min_y_since_cnt, cy)
            self.counted_at_frame[track_id] = (cnt_frame, min_y_since_cnt)

            if (cy - min_y_since_cnt) >= 65 and cy >= (self.tripwire_y + 60):
                self.counted_ids.discard(track_id)
                self.counted_at_frame.pop(track_id, None)
                self.tracker_history[track_id] = []

        self.tracker_history[track_id].append((cx, cy))
        if len(self.tracker_history[track_id]) > 180:
            self.tracker_history[track_id] = [self.tracker_history[track_id][0]] + self.tracker_history[track_id][-179:]
        self.last_seen_frame[track_id] = self._frame_counter
        hist = self.tracker_history[track_id]

        if is_new_track and cy <= config.TRUCK_ENTRANCE_Y + 40:
            radius = getattr(config, "STATIONARY_REID_RADIUS_PX", 55)
            max_age = getattr(config, "STATIONARY_REID_FRAMES", 60)
            for old_id in list(self.counted_ids):
                if old_id == track_id or old_id not in self.tracker_history:
                    continue
                age = self._frame_counter - self.last_seen_frame.get(old_id, -9999)
                if age < 1 or age > max_age:
                    continue
                old_hist = self.tracker_history[old_id]
                lx, ly = old_hist[-1]
                is_stationary = len(old_hist) >= 4 and (
                    np.hypot(lx - old_hist[-4][0], ly - old_hist[-4][1]) < 25
                )
                is_continuation = (
                    age <= 4 and
                    (old_hist[0][1] - ly) >= 60 and
                    abs(cx - lx) <= 90 and
                    (ly - 220) <= cy <= (ly - 25)
                )
                if (is_stationary and np.hypot(cx - lx, cy - ly) <= radius) or is_continuation:
                    self.counted_ids.add(track_id)
                    self.counted_at_frame[track_id] = (self._frame_counter, cy)
                    return False

        if track_id in self.counted_ids or len(hist) < 2:
            return False

        origin_x, origin_y = hist[0]
        prev_y = hist[-2][1]
        dy = prev_y - cy
        tw_y = self.tripwire_y

        chute_crossing = (
            config.COUNT_MIN_X <= cx <= config.COUNT_MAX_X and (
                (prev_y >= tw_y >= cy) or
                (origin_y > tw_y >= cy and dy > 0) or
                any(cy <= max_cy and dy >= min_dy for max_cy, min_dy in config.COUNT_RULES)
            )
        )

        from_side_to_truck = (
            (origin_x < config.CHUTE_MIN_X or origin_x > config.CHUTE_MAX_X) and
            config.COUNT_ENTRY_MIN_X <= cx <= config.COUNT_ENTRY_MAX_X and
            cy <= max(tw_y, config.TRUCK_ENTRANCE_Y)
        )

        min_hits = getattr(config, "DIRECT_THROW_MIN_HITS", 2)
        direct_throw_entry = (
            config.COUNT_ENTRY_MIN_X <= cx <= config.COUNT_ENTRY_MAX_X and
            cy <= config.TRUCK_ENTRANCE_Y and (
                dy >= config.COUNT_ENTRY_MIN_DY or
                (len(hist) >= min_hits and cy <= origin_y)
            )
        )

        if chute_crossing or from_side_to_truck or direct_throw_entry:
            if (self._frame_counter - self.last_counted_frame) < self.count_cooldown_frames:
                return False
            self.last_counted_frame = self._frame_counter
            self.counted_ids.add(track_id)
            self.counted_at_frame[track_id] = (self._frame_counter, cy)
            if not hasattr(self, "track_trajectories"):
                self.track_trajectories = {}
            self.track_trajectories[track_id] = (
                "papan" if chute_crossing else "samping_kembali" if from_side_to_truck else "lempar_langsung"
            )
            return True

        return False

    def process_frame(self, frame: np.ndarray) -> tuple:
        events = []
        if self.tripwire_flash > 0:
            self.tripwire_flash -= 1

        self._frame_counter += 1
        if self._frame_stride > 1 and self._frame_counter % self._frame_stride != 0:
            return frame, []

        fh, fw = frame.shape[:2]
        if hasattr(config, "auto_select_camera_profile"):
            config.auto_select_camera_profile(fw, fh)
        self.active_objects = {}

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

                if cls_name != "pekerja":
                    det_min_x = getattr(config, "DETECTION_MIN_X", 0)
                    det_max_x = getattr(config, "DETECTION_MAX_X", 9999)
                    if not (det_min_x <= cx <= det_max_x):
                        continue

                if cls_name == "es_besar":
                    color = (0, 140, 255)
                    label = f"ES BESAR #{track_id} ({conf:.2f})"
                elif cls_name == "es_kecil":
                    color = (0, 230, 255)
                    label = f"ES KECIL #{track_id} ({conf:.2f})"
                elif cls_name == "pekerja":
                    color = (255, 120, 0)
                    label = f"PEKERJA #{track_id} ({conf:.2f})"
                else:
                    color = (200, 200, 200)
                    label = f"Obj #{track_id} ({conf:.2f})"

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.45, 1)
                cv2.rectangle(frame, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), color, -1)
                cv2.putText(frame, label, (x1 + 2, max(th + 2, y1 - 3)),
                            cv2.FONT_HERSHEY_DUPLEX, 0.45, (0, 0, 0), 1)

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

                should_count = self._record_and_should_count(track_id, cx, cy)
                self.active_objects[track_id]['origin'] = self.tracker_history[track_id][0]

                if should_count:

                    is_stacked = (area >= config.STACKED_AREA_PX)
                    qty = 2 if is_stacked else 1

                    if is_stacked:
                        size = "large"
                        self.total_large += 2
                        logger.warning(
                            f"🧊🧊 [STACKED ICE] 2 Es Bertumpuk #{track_id} terdeteksi "
                            f"(Area={area}px, {w}x{h}) -> Dihitung +2!"
                        )
                    elif cls_name == "es_kecil" or area < config.SMALL_AREA_PX:
                        size = "small"
                        self.total_small += 1
                    else:
                        size = "large"
                        self.total_large += 1

                    self.tripwire_flash = 8

                    crop = frame[max(0, y1):min(fh, y2), max(0, x1):min(fw, x2)].copy()
                    traj = self.track_trajectories.get(track_id, "papan") if hasattr(self, "track_trajectories") else "papan"
                    events.append({
                        'size': size,
                        'area': area,
                        'crop': crop,
                        'track_id': track_id,
                        'conf': conf,
                        'quantity': qty,
                        'is_stacked': is_stacked,
                        'trajectory': traj
                    })
                    logger.info(
                        f"[PURE-YOLO COUNT] {size.upper()} (x{qty}) #{track_id} terhitung | "
                        f"conf={conf:.2f} | BBox=({w}x{h}) | "
                        f"Total: Besar={self.total_large}, Kecil={self.total_small}"
                    )

        if len(self.tracker_history) > 200:
            stale_ids = [tid for tid in self.tracker_history if tid not in active_track_ids]
            for tid in stale_ids[:100]:
                del self.tracker_history[tid]
                self.last_seen_frame.pop(tid, None)
                self.counted_at_frame.pop(tid, None)
                if hasattr(self, "track_trajectories"):
                    self.track_trajectories.pop(tid, None)

        line_col = config.TRIPWIRE_COLOR_ACTIVE if self.tripwire_flash > 0 else config.TRIPWIRE_COLOR_IDLE
        rx, ry, rw, rh = config.ROI
        cv2.line(frame, (rx, self.tripwire_y), (rx + rw, self.tripwire_y), line_col, 2)
        cv2.putText(frame, "PURE YOLO COUNTING LINE", (rx + 5, self.tripwire_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_col, 1)

        return frame, events

PackageDetector = PureYOLOPackageDetector
