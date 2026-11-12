import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 18015):
    ret, frame = cap.read()
    if not ret: break
    if 18007 <= f <= 18014:
        roi, _, _ = det._get_roi(frame)
        fg_mask = det.bg_sub.apply(roi)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, wmask = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
        fg_mask = cv2.bitwise_and(fg_mask, wmask)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, det.morph_kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, det.morph_kernel)
        fg_mask = cv2.dilate(fg_mask, det.morph_kernel, iterations=2)
        cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        raw = []
        for c in cnts:
            a = cv2.contourArea(c)
            if a >= 1800:
                x, y, w, h = cv2.boundingRect(c)
                raw.append((x + w//2, y + h//2, a, (x, y, w, h)))
        dets = det._merge_detections([(r[0], r[1], r[2], r[3], None) for r in raw])
        dets = [d for d in dets if d[2] >= config.MIN_PACKAGE_AREA]
        print(f"F:{f}")
        for oid, o in det.tracker.objects.items():
            print(f"  Tracker Obj {oid}: {o['centroid']} hits={o['hits']} miss={o['missing']}")
        print(f"  Detections: {[(d[0], d[1], d[2], d[3]) for d in dets]}")
    det.process_frame(frame)

