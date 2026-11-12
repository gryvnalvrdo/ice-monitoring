import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 19220):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

for f in range(19220, 19235):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for oid, o in det.tracker.objects.items():
        print(f"F:{f} Obj {oid}: c={o['centroid']} hits={o['hits']} counted={o['counted']} bbox={o['curr_bbox']}")
    for ev in evs:
        print(f"--> F:{f} triggered: {ev}")

