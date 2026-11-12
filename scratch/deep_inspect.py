import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

for f in range(17100, 17950):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print("Starting deep inspect 17950-18040")

for f in range(17950, 18040):
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    
    # We want to see dead objects in this frame before they are deleted
    # Let's inspect tracker directly
    # Call tracker update inside detector
    # To do that cleanly, let's look at detector.process_frame
    ann, events = detector.process_frame(frame)
    if events:
        for ev in events:
            print(f"EVENT at F:{f}: size={ev['size']}, area={ev['area']}")

