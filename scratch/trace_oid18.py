import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

for f in range(17100, 17910):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print("Tracing OID 18 from F:17910...")
for f in range(17910, 17985):
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    ann, events = detector.process_frame(frame)
    if 18 in detector.tracker.objects:
        o = detector.tracker.objects[18]
        print(f"F:{f} OID 18: c={o['centroid']}, bbox={o['curr_bbox']}, min_top={o['min_top']}, hits={o['hits']}, miss={o['missing']}")
    else:
        if f in [17981, 17982, 17983]:
            print(f"F:{f} OID 18 is NOT in tracker (dead)")

