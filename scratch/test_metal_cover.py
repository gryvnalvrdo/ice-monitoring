import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 22350)
det = PackageDetector()
for _ in range(50):
    ret, frame = cap.read()
    det.bg_sub.apply(det._get_roi(frame)[0], learningRate=0.05)

cap.set(cv2.CAP_PROP_POS_FRAMES, 22435)
evs_found = []
for f in range(22435, 22460):
    ret, frame = cap.read()
    if not ret: break
    roi, _, _ = det._get_roi(frame)
    fg_mask = det.bg_sub.apply(roi)
    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, wmask = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
    fg_mask = cv2.bitwise_and(fg_mask, wmask)
    cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    survived = 0
    for c in cnts:
        a = cv2.contourArea(c)
        if a >= 1800:
            x, y, w, h = cv2.boundingRect(c)
            if (h > 10 and (w / h) > 3.5) or (w > 155 and (w / h) > 1.7):
                continue
            survived += 1
    if survived > 0:
        print(f"F:{f} survived contours: {survived}")
print("Done test.")

