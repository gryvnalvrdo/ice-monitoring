import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 19170):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

for f in range(19170, 19300):
    ret, frame = cap.read()
    if not ret: break
    roi, _, _ = det._get_roi(frame)
    fg_mask = det.bg_sub.apply(roi)
    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, white_mask = cv2.threshold(gray_roi, 130, 255, cv2.THRESH_BINARY)
    fg_mask = cv2.bitwise_and(fg_mask, white_mask)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, det.morph_kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, det.morph_kernel)
    fg_mask = cv2.dilate(fg_mask, det.morph_kernel, iterations=2)
    cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    raw = []
    for cnt in cnts:
        a = cv2.contourArea(cnt)
        if a < 1800 or a > config.MAX_PACKAGE_AREA: continue
        x, y, w, h = cv2.boundingRect(cnt)
        if (h > 10 and (w / h) > 3.5) or (w >= 165 and (w / h) >= 1.65): continue
        cx = x + w // 2
        cy = y + h // 2
        if cx > 275 or cy > 320: continue
        raw.append((cx, cy, a, (x, y, w, h)))
    
    merged = det._merge_detections([(cx, cy, a, bb, None) for (cx, cy, a, bb) in raw])
    
    # print when raw has multiple or when merged
    if 19190 <= f <= 19225 or 19260 <= f <= 19290:
        print(f"F:{f} raw={[(cx, cy, int(a), bb) for cx, cy, a, bb in raw]}")
        print(f"      merged={[(m[0], m[1], int(m[2]), m[3]) for m in merged]}")
    det.process_frame(frame)

