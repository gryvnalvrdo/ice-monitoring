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

# Hook logger to capture LINE vs EXIT_TANDEM
counts_data = []

class HookHandler:
    def handle(self, record):
        msg = record.getMessage()
        if "[COUNT]" in msg:
            counts_data.append((detector.total, f, msg))

import logging
hook = HookHandler()
logging.getLogger("detector").addHandler(logging.StreamHandler(sys.stdout))

for f in range(start_f, end_f):
    ret, frame = cap.read()
    if not ret: break
    ann, events = detector.process_frame(frame)

