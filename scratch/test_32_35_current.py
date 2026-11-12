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
    if not ret:
        break
    det.process_frame(frame)

print(f"Done pre-roll to 19180. Count: {det.total}")

for f in range(19180, 19310):
    ret, frame = cap.read()
    if not ret:
        break
    _, evs = det.process_frame(frame)
    for ev in evs:
        print(f"F:{f} Total:{det.total} Large:{det.total_large} Small:{det.total_small} Size:{ev['size']} Area:{ev['area']:.0f}")
