import sys, os
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector
cap = cv2.VideoCapture(config.VIDEO_SOURCE)
fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_frame = int(28.5 * 60 * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
det = PackageDetector()
f = start_frame
while f < start_frame + 2000:
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        size = ev.get('size')
        area = ev.get('area')
        print(f"F:{f} ({f/fps/60:.2f}m) Total:{det.total} {size} area:{area}")
    f += 1
