import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

for f in range(17100, 17915):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print(f"Frame 17915: total={detector.total}")

# We will record for every frame:
# detections list (cx, cy, area, bbox)
# tracked objects (oid, cx, cy, hits, miss, min_top, bbox)
# dead objects in this frame
for f in range(17915, 18040):
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    
    # Let's inspect raw detections before merge and after merge
    # by running detector's logic up to detections
    # ...
    prev_tracked = set(detector.tracker.objects.keys())
    ann, events = detector.process_frame(frame)
    curr_tracked = set(detector.tracker.objects.keys())
    
    if events:
        print(f"\n>>> FRAME {f} EVENT: {events} (Total={detector.total}, B={detector.total_large}, K={detector.total_small})")
    
    # print all objects and detections if in interesting frames
    if f in range(17960, 17990) or f in range(18000, 18040):
        print(f"F:{f} cd={detector.cooldown}:")
        for oid, obj in detector.tracker.objects.items():
            print(f"   oid {oid}: c={obj['centroid']}, hits={obj['hits']}, miss={obj['missing']}, min_top={obj['min_top']}, max_bot={obj['max_bottom']}, area={int(obj['max_area'])}, bbox={obj['curr_bbox']}")

