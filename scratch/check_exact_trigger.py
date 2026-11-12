import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 22350)
det = PackageDetector()
for _ in range(50):
    ret, frame = cap.read()
    det.bg_sub.apply(det._get_roi(frame)[0], learningRate=0.05)

cap.set(cv2.CAP_PROP_POS_FRAMES, 22435)
for f in range(22435, 22450):
    ret, frame = cap.read()
    if not ret: break
    frame_out, evs = det.process_frame(frame)
    if 22441 <= f <= 22445:
        for oid, o in det.tracker.objects.items():
            print(f"F:{f} Obj {oid}: bbox={o['curr_bbox']} c={o['centroid']} hits={o['hits']} counted={o['counted']} area={o['max_area']}")
