import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

config.SIZE_THRESHOLD_AREA = 14000
config.COUNTING_COOLDOWN_FRAMES = 24

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

events = []
for f in range(start_f, int(36.5 * 60 * 10)):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        events.append((det.total, f, round(f/600, 2), ev['size'], round(ev['area'])))

print(f"Total counted with cooldown=24 and thresh=14000: {det.total}")
print(f"Besar: {det.total_large}, Kecil: {det.total_small}")
print("\nAll events:")
for ev in events:
    print(ev)

