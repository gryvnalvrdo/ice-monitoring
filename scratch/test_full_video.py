import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector
from scratch.test_snap_fix import ImprovedTracker

class Tracker18(ImprovedTracker):
    def update(self, detections: list) -> tuple:
        centroids = [(d[0], d[1]) for d in detections]
        dead_objects = []

        if not centroids:
            to_remove = []
            for obj_id, obj in self.objects.items():
                obj['missing'] += 1
                if obj['missing'] > config.TRACKER_MAX_MISSING:
                    to_remove.append(obj_id)
            for obj_id in to_remove:
                dead_objects.append((obj_id, self.objects[obj_id]))
                del self.objects[obj_id]
            return self.objects, dead_objects

        if not self.objects:
            for d in detections:
                self.objects[self.next_id] = self._init_object(d)
                self.next_id += 1
            return self.objects, dead_objects

        obj_ids = list(self.objects.keys())
        obj_cents = [self.objects[oid]['centroid'] for oid in obj_ids]

        used_new = set()
        used_old = set()

        pairs = []
        for i, oc in enumerate(obj_cents):
            oid = obj_ids[i]
            obj = self.objects[oid]
            for j, nc in enumerate(centroids):
                dx = abs(oc[0] - nc[0])
                dy = oc[1] - nc[1]
                min_dy = -18 if (obj['min_top'] <= 80 or oc[1] <= 180) else -25
                if dx > 60 or dy < min_dy or dy > 130:
                    continue
                dist = (dx**2 + dy**2)**0.5
                if dist < config.TRACKER_MAX_DISTANCE:
                    pairs.append((dist, i, j))

        pairs.sort()
        for dist, i, j in pairs:
            if i in used_old or j in used_new:
                continue
            obj_id = obj_ids[i]
            d = detections[j]
            bx, by, bw, bh = d[3]
            bbox_area = bw * bh
            self.objects[obj_id]['prev_centroid'] = self.objects[obj_id]['centroid']
            self.objects[obj_id]['centroid'] = (d[0], d[1])
            self.objects[obj_id]['curr_bbox'] = d[3]
            self.objects[obj_id]['missing'] = 0
            self.objects[obj_id]['hits'] += 1
            self.objects[obj_id]['min_cy'] = min(self.objects[obj_id]['min_cy'], d[1])
            self.objects[obj_id]['min_top'] = min(self.objects[obj_id]['min_top'], d[3][1])
            self.objects[obj_id]['max_bottom'] = max(
                self.objects[obj_id]['max_bottom'], d[3][1] + d[3][3]
            )
            self.objects[obj_id]['area_samples'].append(d[2])
            self.objects[obj_id]['max_bbox_area'] = max(
                self.objects[obj_id]['max_bbox_area'], bbox_area
            )
            if d[2] > self.objects[obj_id]['max_area']:
                self.objects[obj_id]['max_area'] = d[2]
                self.objects[obj_id]['best_bbox'] = d[3]
                self.objects[obj_id]['best_crop'] = d[4]
            if d[2] > self.objects[obj_id]['peak_solo_area']:
                self.objects[obj_id]['peak_solo_area'] = d[2]
            used_old.add(i)
            used_new.add(j)

        to_remove = []
        for i, obj_id in enumerate(obj_ids):
            if i not in used_old:
                self.objects[obj_id]['missing'] += 1
                if self.objects[obj_id]['missing'] > config.TRACKER_MAX_MISSING:
                    to_remove.append(obj_id)
        for obj_id in to_remove:
            dead_objects.append((obj_id, self.objects[obj_id]))
            del self.objects[obj_id]

        for j in range(len(detections)):
            if j not in used_new:
                d = detections[j]
                self.objects[self.next_id] = self._init_object(d)
                self.next_id += 1

        return self.objects, dead_objects

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
end_f = int(37.8 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()
det.tracker = Tracker18()

events = []
for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        events.append((f, det.total, ev['size'], ev['area']))
        print(f"F:{f} ({f/600:.2f}m) Total={det.total} Besar={det.total_large} Kecil={det.total_small} ev={ev['size']} {ev['area']}", flush=True)

print("="*50)
print(f"TOTAL: {det.total} (Besar: {det.total_large}, Kecil: {det.total_small})")

