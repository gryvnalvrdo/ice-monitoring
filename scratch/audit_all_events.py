import sys, os
sys.path.insert(0, os.path.abspath("."))
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
end_f = int(36.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

events_all = []

# Monkey patch _classify_size to log details
orig_process = det.process_frame

for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        events_all.append((f, round(f/600, 2), det.total, det.total_large, det.total_small, ev['size'], round(ev['area'])))

print(f"Total events: {len(events_all)}, Total: {det.total} (Large: {det.total_large}, Small: {det.total_small})")
for e in events_all:
    print(e)

