import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from scratch.test_new_counting_logic import TestDet

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = TestDet()

for f in range(start_f, 19180):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

for f in range(19180, 19310):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        print(f"Triggered at F:{f}: Count {det.total} | {ev['size']} | {ev['area']}")
        for oid, o in det.tracker.objects.items():
            if o['counted']:
                print(f"   counted obj: {oid}, hits={o['hits']} c={o['centroid']} bbox={o['curr_bbox']}")

