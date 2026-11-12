import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2, config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_f = int(28.5 * 60 * fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
det = PackageDetector()

for f in range(start_f, 18045):
    ret, frame = cap.read()
    if not ret: break
    
    if 17945 <= f <= 18040:
        prev_objs = {oid: dict(o) for oid, o in det.tracker.objects.items()}
        frame_out, evs = det.process_frame(frame)
        print(f"F:{f} cd:{det.cooldown} total:{det.total}")
        for oid, o in det.tracker.objects.items():
            print(f"   Obj {oid}: c={o['centroid']} hits={o['hits']} miss={o['missing']} min_cy={o['min_cy']} min_top={o['min_top']} counted={o['counted']}")
        if evs:
            for ev in evs:
                print(f"   *** COUNT EVENT: {ev['size']} {ev['area']} ***")
    else:
        det.process_frame(frame)

