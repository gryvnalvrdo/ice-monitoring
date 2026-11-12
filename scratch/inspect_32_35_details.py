import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
start_f = int(28.5 * 60 * 10)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 19180):
    ret, frame = cap.read()
    if not ret: break
    det.process_frame(frame)

print(f"Pre-roll done up to 19180, total counts so far: {det.total} (B:{det.total_large} K:{det.total_small})")

for f in range(19180, 19300):
    ret, frame = cap.read()
    if not ret: break
    roi, _, _ = det._get_roi(frame)
    fg_mask = det.bg_sub.apply(roi)
    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, wmask = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
    fg_mask = cv2.bitwise_and(fg_mask, wmask)
    cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    cand = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a >= 1800:
            x, y, w, h = cv2.boundingRect(c)
            cand.append((x, y, w, h, a))
            
    _, evs = det.process_frame(frame)
    for ev in evs:
        print(f"--> EVENT at F:{f}: Count {det.total} | {ev['size'].upper()} | area={ev['area']:.1f}")
        
    if 19195 <= f <= 19225 or 19260 <= f <= 19295:
        objs = [(oid, o['centroid'], o['hits'], o['counted'], o['curr_bbox']) for oid, o in det.tracker.objects.items()]
        print(f"F:{f} cand={cand} | tracked={objs}")

