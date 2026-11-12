import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
det = PackageDetector()

for f in range(17100, 17185):
    ret, frame = cap.read()
    if not ret: break
    frame_out, evs = det.process_frame(frame)
    if 17145 <= f <= 17184:
        print(f"F:{f} cd:{det.cooldown}")
        for oid, o in det.tracker.objects.items():
            print(f"   Obj {oid}: c={o['centroid']} hits={o['hits']} miss={o['missing']} counted={o['counted']} area={o['max_area']}")
        if evs:
            for ev in evs:
                print(f"   *** COUNT EVENT: Total={det.total} {ev['size']} {ev['area']} ***")
