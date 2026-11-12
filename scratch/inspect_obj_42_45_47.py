import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
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

for f in range(19180, 19300):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for oid, o in det.tracker.objects.items():
        if oid in (42, 45, 47):
            print(f"F:{f} Obj {oid}: c={o['centroid']} bbox={o['curr_bbox']} hits={o['hits']} counted={o['counted']} first_cy={o['first_cy']} min_top={o['min_top']} max_bottom={o['max_bottom']}")

