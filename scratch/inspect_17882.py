import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17850)
detector = PackageDetector()

for f in range(17850, 17920):
    ret, frame = cap.read()
    if not ret: break
    ann, events = detector.process_frame(frame)
    if events:
        print(f"F:{f} EVENT: {events}")
    for oid, o in detector.tracker.objects.items():
        if f in range(17875, 17890):
            print(f"F:{f} oid {oid}: c={o['centroid']}, min_top={o['min_top']}, cy={o['centroid'][1]}, min_cy={o['min_cy']}, first_cy={o['first_cy']}, miss={o['missing']}, hits={o['hits']}")

