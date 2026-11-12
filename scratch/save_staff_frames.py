import sys
sys.path.append(r"c:\Users\alver\OneDrive\Documents\Projects\camera")
import cv2

cap = cv2.VideoCapture("XVR_ch3_main_20261022200001_20261022203800.mp4")

# Let's save full images with staff around the truck door from 19190 to 19290
for f in range(19190, 19295, 5):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if ret:
        # crop upper area where staff and truck door are (y: 600 to 1450, x: 250 to 750)
        crop = frame[600:1450, 250:750]
        cv2.imwrite(f"scratch/audit_32_35/staff_{f}.jpg", crop)

print("Saved staff frames 19190 to 19290")

