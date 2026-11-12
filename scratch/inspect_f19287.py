import sys, os
sys.path.insert(0, os.path.abspath("."))
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 19180):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

for f in range(19180, 19310):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    if evs:
        print(f"Triggered at F:{f}: Total={det.total}")
        for oid, o in det.tracker.objects.items():
            if o['counted']:
                print(f"  oid={oid}: hits={o['hits']}, first_cy={o['first_cy']}, min_cy={o['min_cy']}, disp={o['first_cy']-o['min_cy']}, max_bottom={o['max_bottom']}, cy={o['centroid'][1]}")

