import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 19000)
det = PackageDetector()

for f in range(19000, 19300):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        print(f"Triggered at F:{f}: Count {det.total} | {ev['size']} | {ev['area']}")
    for oid, o in det.tracker.objects.items():
        if oid in (40, 42, 43, 44, 45, 0, 1, 2, 3):
            if f % 10 == 0:
                print(f"  F:{f} Obj {oid}: c={o['centroid']} hits={o['hits']} counted={o['counted']} bbox={o['curr_bbox']}")

