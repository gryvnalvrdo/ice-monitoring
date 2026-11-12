import sys, os
sys.path.insert(0, os.path.abspath("."))
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 19185):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

print("Starting tracking log:")
for f in range(19185, 19300):
    ret, frame = cap.read()
    if not ret: break
    roi, _, _ = det._get_roi(frame)
    _, evs = det.process_frame(frame)
    if evs:
        for ev in evs:
            print(f"*** EVENT at F:{f}: Total={det.total}, size={ev['size']}, area={ev['area']}")
    for oid, o in det.tracker.objects.items():
        if oid in (40, 42, 45, 47):
            print(f"  F:{f} oid={oid} hits={o['hits']} c={o['centroid']} dy={o['prev_centroid'][1]-o['centroid'][1] if o['prev_centroid'] else 0} counted={o['counted']} bbox={o['curr_bbox']}")

