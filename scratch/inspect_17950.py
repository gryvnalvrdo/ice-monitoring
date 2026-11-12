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
    
    if 17945 <= f <= 18035:
        roi, _, _ = det._get_roi(frame)
        fg_mask, detections = det._preprocess_and_detect(roi)
        print(f"--- FRAME {f} (cooldown: {det.cooldown_counter}) ---")
        for obj_id, obj in det.tracked_objects.items():
            print(f"  Tracked {obj_id}: cy={obj['cy']} hits={obj['hits']} min_cy={obj['min_cy']} min_top={obj['min_top']} first_cy={obj['first_cy']}")
        for d in detections:
            print(f"  Det: rect={d['rect']} area={d['area']} cx={d['cx']} cy={d['cy']}")
            
        _, evs = det.process_frame(frame)
        if evs:
            for ev in evs:
                print(f"  >>> COUNT EVENT: Total={det.total} {ev['size']} area={ev['area']}")
    else:
        det.process_frame(frame)
