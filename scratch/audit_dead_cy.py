import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

dead_stats = []
for f in range(start_f, int(36.5 * 60 * 10)):
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
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw = []
    for cnt in contours:
        a = cv2.contourArea(cnt)
        if a < 1800 or a > config.MAX_PACKAGE_AREA: continue
        x, y, w, h = cv2.boundingRect(cnt)
        if (h > 10 and (w / h) > 3.5) or (w >= 165 and (w / h) >= 1.65): continue
        cx = x + w // 2
        cy = y + h // 2
        if cx > 275 or cy > 320: continue
        raw.append((cx, cy, a, (x, y, w, h), None))
    detections = det._merge_detections(raw)
    detections = [d for d in detections if config.MIN_PACKAGE_AREA <= d[2] <= config.MAX_PACKAGE_AREA and not (d[3][2] >= 165 and d[3][2] / d[3][3] >= 1.65)]
    tracked, dead_objects = det.tracker.update(detections)
    
    for oid, o in dead_objects:
        if not o['counted'] and o['hits'] >= 4 and config.MIN_PACKAGE_AREA <= o['max_area'] <= config.MAX_PACKAGE_AREA:
            dead_stats.append((f, oid, o['centroid'][1], o['min_cy'], o['first_cy'], o['first_cy'] - o['min_cy'], o['curr_bbox']))

print(f"Total dead objects meeting baseline: {len(dead_stats)}")
for ds in dead_stats:
    print(f"F:{ds[0]} Obj {ds[1]}: last_cy={ds[2]}, min_cy={ds[3]}, first_cy={ds[4]}, disp={ds[5]}, bbox={ds[6]}")

