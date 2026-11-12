import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

for f in range(17100, 17990):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print('Tracing 17990 to 18040 dead objects:')
# Let's inspect tracker directly by monkeypatching tracker.update or wrapping it
orig_update = detector.tracker.update

def logged_update(detections):
    tracked, dead = orig_update(detections)
    if dead:
        for did, d_obj in dead:
            print(f"F:{curr_f} DEAD oid={did}, hits={d_obj['hits']}, min_top={d_obj['min_top']}, cy={d_obj['centroid'][1]}, min_cy={d_obj['min_cy']}, first_cy={d_obj['first_cy']}, max_bot={d_obj['max_bottom']}, area={int(d_obj['max_area'])}")
    return tracked, dead

detector.tracker.update = logged_update

for f in range(17990, 18040):
    curr_f = f
    ret, frame = cap.read()
    if not ret: break
    ann, events = detector.process_frame(frame)
    if events:
        print(f"   >>> F:{f} EVENT: {events}")

