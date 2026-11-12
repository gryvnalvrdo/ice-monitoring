import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

for f in range(17100, 17920):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print("Tracing OID 20 from F:17920...")
for f in range(17920, 17975):
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    ann, events = detector.process_frame(frame)
    if 20 in detector.tracker.objects:
        o = detector.tracker.objects[20]
        print(f"F:{f} OID 20: c={o['centroid']}, bbox={o['curr_bbox']}, min_top={o['min_top']}, hits={o['hits']}, miss={o['missing']}")
    else:
        if f in range(17965, 17972):
            print(f"F:{f} OID 20 is dead")

