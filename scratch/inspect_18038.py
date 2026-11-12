import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector
from scratch.test_snap_fix import ImprovedTracker

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_f = int(28.5 * 60 * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

det = PackageDetector()
det.tracker = ImprovedTracker()

for f in range(start_f, 18050):
    ret, frame = cap.read()
    if not ret: break
    if 18015 <= f <= 18045:
        print(f"--- FRAME {f} cd={det.cooldown} ---")
        for oid, o in det.tracker.objects.items():
            print(f"  Obj {oid}: c={o['centroid']} hits={o['hits']} miss={o['missing']} min_cy={o['min_cy']} min_top={o['min_top']} counted={o['counted']} area={o['max_area']}")
        _, evs = det.process_frame(frame)
        if evs:
            for ev in evs:
                print(f"  >>> COUNT EVENT: Total={det.total} {ev['size']} area={ev['area']}")
    else:
        det.process_frame(frame)

