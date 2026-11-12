import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, int(37.8 * 60 * 10)):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        if det.total >= 59:
            print(f"Count {det.total} at F:{f}: area={ev['area']} size={ev['size']}", flush=True)
