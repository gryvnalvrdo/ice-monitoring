import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_f = int(28.5 * 60 * src_fps)
end_f = int(37.8 * 60 * src_fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

detector = PackageDetector()

line_counts = []
exit_counts = []

f = start_f
while f < end_f:
    ret, frame = cap.read()
    if not ret: break
    
    # We can capture events from detector.process_frame
    prev_total = detector.total
    ann, events = detector.process_frame(frame)
    if events:
        for ev in events:
            # Check how it was counted: if tripwire_flash == 8 right now
            # In detector.py logger.info says (LINE) or (EXIT_TANDEM)
            pass
    f += 1

cap.release()

