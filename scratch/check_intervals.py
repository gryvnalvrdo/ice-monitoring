import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

# Let's inspect the intervals between bags in the video
# Bag 1: 17110
# Bag 2: 17132 (diff = 22 frames = 2.2s)
# Bag 3: 17149 (diff = 17 frames = 1.7s)
# Bag 4: 17170 (diff = 21 frames = 2.1s)
# Bag 5: 17495
# Bag 6: 17539 (diff = 44 frames = 4.4s)
# Bag 7: 17568 (diff = 29 frames = 2.9s)
# Bag 8: 17624 (diff = 56 frames = 5.6s)
# Bag 9: 17647 (diff = 23 frames = 2.3s)
# Bag 10: 17678 (diff = 31 frames = 3.1s)
# Bag 11: 17702 (diff = 24 frames = 2.4s)
# Bag 12: 17733 (diff = 31 frames = 3.1s)
# Bag 13: 17762 (diff = 29 frames = 2.9s)
# Bag 14: 17805 (diff = 43 frames = 4.3s)
# Bag 15: 17839 (diff = 34 frames = 3.4s)
# Bag 16: 17882 (diff = 43 frames = 4.3s)
# Bag 17: 17914 (diff = 32 frames = 3.2s)
# Then Bag 18 was pulled at 17970-17982
# Bag 19 was pulled at 18005-18035
print('Done listing')

