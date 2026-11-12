import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

max_w = 0
for f in range(start_f, 21700):
    ret, frame = cap.read()
    if not ret: break
    roi, _, _ = det._get_roi(frame)
    fg_mask = det.bg_sub.apply(roi)
    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, wmask = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
    fg_mask = cv2.bitwise_and(fg_mask, wmask)
    cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        a = cv2.contourArea(c)
        if a >= 2500:
            x, y, w, h = cv2.boundingRect(c)
            if w > max_w:
                max_w = w
    det.process_frame(frame)

print("Max bbox width among all real packages:", max_w)

