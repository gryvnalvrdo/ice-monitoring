import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
import os
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_f = int(28.5 * 60 * fps)
end_f = int(37.8 * 60 * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

det = PackageDetector()
records = []

os.makedirs("scratch/gt_audit", exist_ok=True)

for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret: break
    frame_out, evs = det.process_frame(frame)
    for ev in evs:
        cnt_idx = det.total
        sz = ev['size']
        ar = ev['area']
        m = f / fps / 60
        s = f / fps
        records.append((cnt_idx, f, m, s, sz, ar))
        # Save a crop of the frame showing the loaded bag
        roi = frame[1050:1450, 420:720]
        cv2.imwrite(f"scratch/gt_audit/count_{cnt_idx:02d}_f{f}_{sz}.jpg", roi)

print(f"Total events recorded: {len(records)}")
with open("scratch/gt_audit/events.txt", "w") as out:
    for r in records:
        out.write(f"Count {r[0]:02d} | Frame {r[1]} ({int(r[2])}:{int(r[3]%60):02d}) | {r[4].upper()} | Area: {r[5]:.0f} px\n")
print("Saved events.txt and images.")

