import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

for f in range(17100, 17870):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print("At 17870:")
orig_update = detector.tracker.update
def my_update(dets):
    t, d = orig_update(dets)
    if d:
        for did, obj in d:
            print(f"F:{curr_f} DEAD: oid={did}, hits={obj['hits']}, min_top={obj['min_top']}, cy={obj['centroid'][1]}, min_cy={obj['min_cy']}, first_cy={obj['first_cy']}, max_bot={obj['max_bottom']}, area={int(obj['max_area'])}")
    return t, d

detector.tracker.update = my_update

for f in range(17870, 17895):
    curr_f = f
    ret, frame = cap.read()
    if not ret: break
    ann, events = detector.process_frame(frame)
    if events:
        print(f"F:{f} EVENT: {events}")

