import cv2, os, sys
sys.path.insert(0, '.')
import config

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0

out_dir = r'C:\Users\alver\.gemini\antigravity\brain\84fc56d5-7b41-4e5a-b998-c886527add96\scratch\inspect_gap'
os.makedirs(out_dir, exist_ok=True)

# Sample every 50 frames from 21160 to 22450 (about every 5 seconds)
for f in range(21160, 22450, 50):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ret, frame = cap.read()
    if not ret: break
    sec = f / src_fps
    chute = frame[650:1450, 250:800].copy()
    cv2.putText(chute, f"F:{f} T:{int(sec//60):02d}:{sec%60:04.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.imwrite(os.path.join(out_dir, f"f_{f}.jpg"), chute)

cap.release()
print("Saved gap sample frames")

