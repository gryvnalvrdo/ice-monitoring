import cv2, os

cap = cv2.VideoCapture("XVR_ch3_main_20261022200001_20261022203800.mp4")
os.makedirs("scratch/start_setup", exist_ok=True)

for f in range(17090, 17210, 10):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"scratch/start_setup/f_{f}.jpg", frame[600:1450, 250:750])

print("Saved frames 17090 to 17200")

