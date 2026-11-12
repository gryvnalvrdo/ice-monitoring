import cv2, os, sys
sys.path.insert(0, '.')
import config

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 21270)
ret, frame = cap.read()

roi = frame[1050:1420, 420:700]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

print("Gray stats for upper half y=0..150:")
upper = gray[0:150, 100:250]
print("min:", upper.min(), "max:", upper.max(), "mean:", upper.mean())

# Check background model!
# When warmup was run, was that bag ALREADY sitting in the chute?!

