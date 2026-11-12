import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
import numpy as np

cap = cv2.VideoCapture(config.VIDEO_SOURCE)

gaps = [
    ("Gap 1 (28:38 - 29:09)", 17180, 17495),
    ("Gap 2 (30:02 - 31:03)", 18025, 18632),
    ("Gap 3 (32:08 - 33:57)", 19287, 20378),
    ("Gap 4 (34:44 - 34:55)", 20846, 20954),
    ("Gap 5 (35:31 - 35:49)", 21310, 21498),
    ("Gap 6 (36:07 - 37:24)", 21671, 22442),
    ("Gap 7 (37:24 - 37:48)", 22442, 22680),
]

for name, start, end in gaps:
    print(f"\nChecking {name} (Frames {start} to {end})...")
    # Sample every 10 frames, check max brightness in chute ROI
    max_white_pixels = 0
    max_frame = start
    for f in range(start, end, 5):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret: break
        roi = frame[1050:1450, 420:720]
        # Chute area: x=50:230, y=50:250
        chute = roi[50:250, 50:230]
        gray = cv2.cvtColor(chute, cv2.COLOR_BGR2GRAY)
        white_count = np.sum(gray > 130)
        if white_count > max_white_pixels:
            max_white_pixels = white_count
            max_frame = f
    print(f"  Max white pixels in chute: {max_white_pixels} at Frame {max_frame} ({max_frame/10/60:.2f}m)")

