import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector
cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
det = PackageDetector()
for f in range(17100, 18300):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        sz = ev.get('size')
        ar = ev.get('area')
        print(f"Frame {f} ({f/10/60:.2f}m / {f/10:.1f}s): Count={det.total} Large={det.total_large} Small={det.total_small} size={sz} area={ar}")

