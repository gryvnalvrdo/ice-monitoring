import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

# Let's test different min_top thresholds: e.g. 60, 65
for threshold in [55, 60, 62, 65, 70]:
    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_f = int(28.5 * 60 * src_fps)
    end_f = int(37.8 * 60 * src_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

    detector = PackageDetector()
    
    # We will modify cond_a min_top threshold dynamically
    # Let's patch process_frame or run detector with patched cond_a
    # We can inspect events
    events_list = []
    
    f = start_f
    while f < end_f:
        ret, frame = cap.read()
        if not ret: break
        
        # We can temporarily patch cond_a in detector by modifying dead_objects check
        # Let's see: in detector.py, cond_a uses 85:
        # cond_a = (min_top <= 85 or (cy <= 120 and min_top <= 95))
        # Let's see what happens if min_top <= threshold
        f += 1
    cap.release()

