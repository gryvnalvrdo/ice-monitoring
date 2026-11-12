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

print(f"Frame 19180 reached. det.total = {det.total}")

for f in range(19180, 19300):
    ret, frame = cap.read()
    if not ret: break
    _, evs = det.process_frame(frame)
    for ev in evs:
        print(f"--> Count {det.total} at F:{f} (min {f/600:.2f}): size={ev['size']} area={ev['area']}")
    for oid, o in det.tracker.objects.items():
        if f in (19198, 19199, 19200, 19216, 19217, 19218, 19264, 19265, 19266, 19286, 19287, 19288):
            print(f"   F:{f} Obj {oid}: c={o['centroid']} prev={o['prev_centroid']} hits={o['hits']} counted={o['counted']} bbox={o['curr_bbox']} area={o['max_area']}")

