import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

class PreciseDetector(PackageDetector):
    def _classify_size(self, obj: dict) -> str:
        samples = obj.get('area_samples', [])
        peak_solo = obj.get('peak_solo_area', obj['max_area'])
        max_bbox = obj.get('max_bbox_area', 0)

        if len(samples) >= 5:
            sorted_s = sorted(samples)
            trim = max(1, len(sorted_s) // 5)
            trimmed = sorted_s[trim:-trim] if len(sorted_s) > 2 * trim else sorted_s
            representative = sorted_s[int(len(sorted_s) * 0.75)]
        else:
            representative = peak_solo

        votes_large = 0
        votes_small = 0

        thresh = config.SIZE_THRESHOLD_AREA  # which we will set to 14000

        if representative >= thresh:
            votes_large += 2
        else:
            votes_small += 2

        if peak_solo >= thresh:
            votes_large += 1
        else:
            votes_small += 1

        if max_bbox >= thresh * 1.2:
            votes_large += 1
        elif max_bbox > 0 and max_bbox < thresh * 0.85:
            votes_small += 1

        return 'large' if votes_large >= votes_small else 'small'

    def process_frame(self, frame):
        events = []

        if self.cooldown > 0:
            self.cooldown -= 1
        if self.tripwire_flash > 0:
            self.tripwire_flash -= 1

        roi, ox, oy = self._get_roi(frame)

        if not self.is_warmed_up:
            for _ in range(15):
                self.bg_sub.apply(roi, learningRate=0.25)
            self.is_warmed_up = True

        fg_mask = self.bg_sub.apply(roi)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, white_mask = cv2.threshold(gray_roi, 130, 255, cv2.THRESH_BINARY)
        fg_mask = cv2.bitwise_and(fg_mask, white_mask)

        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.morph_kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.morph_kernel)
        fg_mask = cv2.dilate(fg_mask, self.morph_kernel, iterations=2)

        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        raw_detections = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 1800 or area > config.MAX_PACKAGE_AREA:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            cx = x + w // 2
            cy = y + h // 2

            if cx > 275 or cy > 320:
                continue

            if y + h >= roi.shape[0] - 6 and h < 70:
                continue

            if (h > 10 and (w / h) > 3.5) or (w >= 165 and (w / h) >= 1.65):
                continue

            mask_cnt = np.zeros(roi.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_cnt, [cnt], -1, 255, -1)
            mean_sat = cv2.mean(hsv_roi[:, :, 1], mask=mask_cnt)[0]
            mean_b = cv2.mean(roi[:, :, 0], mask=mask_cnt)[0]
            mean_r = cv2.mean(roi[:, :, 2], mask=mask_cnt)[0]
            if mean_sat > 50 and (mean_b - mean_r) > 25:
                continue

            crop = roi[max(0, y):min(roi.shape[0], y+h),
                       max(0, x):min(roi.shape[1], x+w)].copy()
            raw_detections.append((cx, cy, area, (x, y, w, h), crop))

        detections = self._merge_detections(raw_detections)
        detections = [d for d in detections if config.MIN_PACKAGE_AREA <= d[2] <= config.MAX_PACKAGE_AREA and not (d[3][2] >= 165 and d[3][2] / d[3][3] >= 1.65)]
        tracked, dead_objects = self.tracker.update(detections)
        tripwire_y = config.TRIPWIRE_Y

        for obj_id, obj in tracked.items():
            if obj['hits'] < config.TRACKER_MIN_HITS or obj['counted']:
                continue

            cx, cy = obj['centroid']
            prev = obj['prev_centroid']
            if prev is None:
                continue

            prev_y = prev[1]
            dy = prev_y - cy

            crossed = (prev_y >= tripwire_y >= cy) or (cy <= tripwire_y and prev_y >= tripwire_y - 40 and dy > 0)
            disp = obj['first_cy'] - obj['min_cy']

            if crossed and dy >= 5 and 110 <= cx <= 265 and obj['max_area'] <= config.MAX_PACKAGE_AREA:
                if (obj['max_bottom'] >= 180 or obj['first_cy'] >= 160) and disp >= 45 and cy <= 95:
                    if self.cooldown == 0:
                        size = self._classify_size(obj)
                        max_area = obj['max_area']
                        crop_img = obj['best_crop']

                        if size == 'large':
                            self.total_large += 1
                        else:
                            self.total_small += 1

                        self.tracker.mark_counted(obj_id)
                        self.cooldown = config.COUNTING_COOLDOWN_FRAMES
                        self.tripwire_flash = 8

                        events.append({'size': size, 'area': max_area, 'crop': crop_img})

        for obj_id, obj in dead_objects:
            if obj['counted']:
                continue
            min_top = obj['min_top']
            cy = obj['centroid'][1]
            cx = obj['centroid'][0]
            ma = obj['max_area']
            hits = obj['hits']
            disp = obj['first_cy'] - obj['min_cy']

            # Only count as dead object if it actually exited at the top (last cy <= 85)
            if hits >= 4 and config.MIN_PACKAGE_AREA <= ma <= config.MAX_PACKAGE_AREA and 110 <= cx <= 265:
                cond_exit = cy <= 85 and disp >= 45 and (obj['first_cy'] >= 160 or obj['max_bottom'] >= 180)
                if cond_exit and self.cooldown == 0:
                    size = self._classify_size(obj)
                    crop_img = obj['best_crop']

                    if size == 'large':
                        self.total_large += 1
                    else:
                        self.total_small += 1

                    self.cooldown = config.COUNTING_COOLDOWN_FRAMES
                    self.tripwire_flash = 8

                    events.append({'size': size, 'area': ma, 'crop': crop_img})

        return frame, events

config.SIZE_THRESHOLD_AREA = 14000
cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PreciseDetector()
import numpy as np

for f in range(start_f, 19180):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

print(f"Pre-roll up to 19180 done. Count: {det.total}")
sub_evs = []
for f in range(19180, 19310):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        sub_evs.append((f, det.total, ev['size'], round(ev['area'])))

print("Events between 19180 and 19310:")
for se in sub_evs:
    print(se)

