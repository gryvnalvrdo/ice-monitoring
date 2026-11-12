import sys, os
sys.path.insert(0, os.path.abspath("."))
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
end_f = int(36.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

records = []
for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        for oid, o in det.tracker.objects.items():
            if o['counted'] and o['hits'] >= 2 and abs(o['max_area'] - ev['area']) < 1.0:
                records.append({
                    'total': det.total,
                    'frame': f,
                    'min': round(f/600, 2),
                    'size': ev['size'],
                    'area': round(ev['area']),
                    'first_cy': o['first_cy'],
                    'min_cy': o['min_cy'],
                    'disp': o['first_cy'] - o['min_cy'],
                    'min_top': o['min_top'],
                    'max_bottom': o['max_bottom'],
                    'curr_cy': o['centroid'][1],
                    'hits': o['hits']
                })
                break

print(f"Total counted: {len(records)}, Large: {det.total_large}, Small: {det.total_small}")
for r in records:
    print(r)
