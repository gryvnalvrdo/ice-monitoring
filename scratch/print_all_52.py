import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_f = int(28.5 * 60 * src_fps)
end_f = int(37.8 * 60 * src_fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

detector = PackageDetector()

for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret: break
    ann, events = detector.process_frame(frame)
    if events:
        for ev in events:
            sec = f / src_fps
            print(f"[{detector.total:2d}] F:{f} T:{int(sec//60):02d}:{sec%60:04.1f} | {ev['size'].upper():5s} area={ev['area']:6.0f} | B={detector.total_large} K={detector.total_small}")

