import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 20660)

out_dir = r'C:\Users\alver\.gemini\antigravity\brain\84fc56d5-7b41-4e5a-b998-c886527add96\scratch\inspect_20676'
os.makedirs(out_dir, exist_ok=True)

for f in range(20665, 20705, 2):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if not ret: break
    chute = frame[650:1450, 300:750]
    cv2.putText(chute, f'F:{f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    cv2.imwrite(os.path.join(out_dir, f'raw_{f}.jpg'), chute)

cap.release()
print('Saved 20665-20705 frames')

