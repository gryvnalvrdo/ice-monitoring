import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_f = int(28.5 * 60 * src_fps)
end_f = int(37.8 * 60 * src_fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, 18000)

detector = PackageDetector()
# We can fast-forward or run from 17100

