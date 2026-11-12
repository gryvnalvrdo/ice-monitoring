import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 17100)
detector = PackageDetector()

out_dir = r'C:\Users\alver\.gemini\antigravity\brain\84fc56d5-7b41-4e5a-b998-c886527add96\scratch\mog2_proof'
os.makedirs(out_dir, exist_ok=True)

# Run up to 21250
for f in range(17100, 21260):
    ret, frame = cap.read()
    if not ret: break
    detector.process_frame(frame)

print("Reached 21260 in real simulation.")

# Now save masks for 21260 to 21330
for f in range(21260, 21330, 5):
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    fg = detector.bg_sub.apply(roi)
    cv2.imwrite(os.path.join(out_dir, f"fg_{f}.jpg"), fg)
    
    # Also get background image
    bg_img = detector.bg_sub.getBackgroundImage()
    cv2.imwrite(os.path.join(out_dir, f"bg_{f}.jpg"), bg_img)

cap.release()
print("Saved real MOG2 background and foreground masks")

