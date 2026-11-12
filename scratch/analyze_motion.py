import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

# We will test tracking with velocity tracking on the frames
cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

# Let's inspect objects in dead_objects when they die:
# Record:
# 1. total upward movement: first_cy - min_cy
# 2. recent upward movement: centroid_y 5 frames ago - last centroid_y
# 3. min_top
# 4. min_cy
# 5. was it counted?

