import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 21265)

detector = PackageDetector()
out_dir = r'C:\Users\alver\.gemini\antigravity\brain\84fc56d5-7b41-4e5a-b998-c886527add96\scratch\inspect_masks'
os.makedirs(out_dir, exist_ok=True)

for f in range(21265, 21320, 5):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    fg = detector.bg_sub.apply(roi)
    _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, wm = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
    mask = cv2.bitwise_and(fg, wm)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, detector.morph_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, detector.morph_kernel)
    mask = cv2.dilate(mask, detector.morph_kernel, iterations=2)
    
    cv2.imwrite(os.path.join(out_dir, f"roi_{f}.jpg"), roi)
    cv2.imwrite(os.path.join(out_dir, f"mask_{f}.jpg"), mask)

cap.release()
print("Saved masks")

