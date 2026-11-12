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

for f in range(17915, 18010):
    ret, frame = cap.read()
    if not ret: break
    ann, events = detector.process_frame(frame)
    if events:
        print(f"*** FRAME {f}: EVENT {events} -> Total={detector.total}")
        for oid, o in detector.tracker.objects.items():
            print(f"    alive oid {oid}: hits={o['hits']}, miss={o['missing']}, c={o['centroid']}, min_top={o['min_top']}, max_bot={o['max_bottom']}, min_cy={o['min_cy']}, first_cy={o['first_cy']}, cnt={o['counted']}, max_area={o['max_area']}")

