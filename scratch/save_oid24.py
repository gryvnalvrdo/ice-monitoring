import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 18005)

out_dir = r'C:\Users\alver\.gemini\antigravity\brain\84fc56d5-7b41-4e5a-b998-c886527add96\scratch\inspect_oid24'
os.makedirs(out_dir, exist_ok=True)

for f in range(18006, 18025):
    ret, frame = cap.read()
    if not ret: break
    cv2.imwrite(os.path.join(out_dir, f'f_{f}.jpg'), frame[650:1450, 300:750])

cap.release()
print('Saved oid24 frames')

