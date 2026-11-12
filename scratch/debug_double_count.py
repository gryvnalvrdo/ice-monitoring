import cv2
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from detector import PackageDetector

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_frame = int(28.5 * 60 * src_fps)
end_frame = int(37.8 * 60 * src_fps)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

detector = PackageDetector()

f_idx = 0
events_log = []

while True:
    ret, frame = cap.read()
    if not ret:
        break
    curr_frame_no = start_frame + f_idx
    if curr_frame_no > end_frame:
        break

    prev_total = detector.total
    frame, events = detector.process_frame(frame)

    for ev in events:
        src_sec = curr_frame_no / src_fps
        events_log.append({
            'frame': curr_frame_no,
            'time': f"{int(src_sec//60):02d}:{src_sec%60:05.2f}",
            'size': ev['size'],
            'area': ev['area'],
            'total': detector.total,
            'besar': detector.total_large,
            'kecil': detector.total_small,
        })
        print(
            f"[{len(events_log):3d}] F:{curr_frame_no} T:{src_sec/60:.2f}min "
            f"| {ev['size'].upper():5s} area={ev['area']:7.0f} "
            f"| TOTAL={detector.total} (B={detector.total_large} K={detector.total_small})"
        )

    f_idx += 1

cap.release()

print("\n--- RINGKASAN KEJADIAN MENCURIGAKAN ---")
for i in range(1, len(events_log)):
    prev = events_log[i-1]
    curr = events_log[i]
    gap_frames = curr['frame'] - prev['frame']
    if gap_frames < 15:
        print(
            f"  !! JARAK PENDEK {gap_frames} frame antara hitungan {prev['total']-1}->{prev['total']} "
            f"(area={prev['area']:.0f}) dan {curr['total']-1}->{curr['total']} (area={curr['area']:.0f}) "
            f"@ F:{curr['frame']} T:{curr['time']}"
        )

