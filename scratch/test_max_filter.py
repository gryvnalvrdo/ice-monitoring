import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

config.MAX_PACKAGE_AREA = 38000

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 22400)
det = PackageDetector()
for _ in range(50):
    det.bg_sub.apply(det._get_roi(cap.read()[1])[0], learningRate=0.05)

found = 0
for f in range(22400, 22500):
    ret, frame = cap.read()
    if not ret: break
    frame_out, evs = det.process_frame(frame)
    for ev in evs:
        print(f"F:{f} ev={ev['size']} area={ev['area']}")
        found += 1
print("Events found:", found)

