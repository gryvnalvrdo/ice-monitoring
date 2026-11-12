import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_POS_FRAMES, 21200)

detector = PackageDetector()

# Warmup bg_sub on 21200
ret, frame = cap.read()
roi, _, _ = detector._get_roi(frame)
for _ in range(30):
    detector.bg_sub.apply(roi, learningRate=0.1)

print("Tracking frames 21250 to 21450:")

for f in range(21250, 21450):
    ret, frame = cap.read()
    if not ret: break
    roi, ox, oy = detector._get_roi(frame)
    
    fg_mask = detector.bg_sub.apply(roi)
    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, white_mask = cv2.threshold(gray_roi, 130, 255, cv2.THRESH_BINARY)
    fg_mask = cv2.bitwise_and(fg_mask, white_mask)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, detector.morph_kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, detector.morph_kernel)
    fg_mask = cv2.dilate(fg_mask, detector.morph_kernel, iterations=2)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    dets = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        x, y, w, h = cv2.boundingRect(cnt)
        cx, cy = x + w // 2, y + h // 2
        dets.append((cx, cy, int(area), (x, y, w, h)))

    ann, events = detector.process_frame(frame)
    if events:
        print(f"*** F:{f} EVENT: {events}")
    
    if len(dets) > 0 and (f % 5 == 0 or events):
        print(f"F:{f} Dets: {dets}")
        for oid, o in detector.tracker.objects.items():
            print(f"   oid {oid}: c={o['centroid']}, hits={o['hits']}, miss={o['missing']}, min_top={o['min_top']}, cy={o['centroid'][1]}")

