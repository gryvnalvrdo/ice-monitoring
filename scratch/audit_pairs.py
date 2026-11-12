import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config, os

cap = cv2.VideoCapture(config.VIDEO_SOURCE)

pairs = [
    ("Pair 1 (Counts 3 & 4)", 17155, 17195),
    ("Pair 2 (Counts 27 & 28)", 18950, 18990),
    ("Pair 3 (Counts 32 & 33)", 19190, 19230),
    ("Pair 4 (Counts 41 & 42)", 20635, 20675),
]

for name, s, e in pairs:
    os.makedirs(f"scratch/audit_pair_{s}", exist_ok=True)
    for f in range(s, e, 3):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(f"scratch/audit_pair_{s}/f_{f}.jpg", frame[1050:1450, 420:720])
    print(f"Saved {name}")
