import cv2
import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.DEBUG, format='%(message)s')

import config
from detector import PackageDetector

OUT_DIR = r"C:\Users\alver\.gemini\antigravity\brain\84fc56d5-7b41-4e5a-b998-c886527add96\scratch"
os.makedirs(OUT_DIR, exist_ok=True)

FOCUS_START = 17900
FOCUS_END = 18050

cap = cv2.VideoCapture(config.VIDEO_SOURCE)
src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
start_frame = int(28.5 * 60 * src_fps)

cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

detector = PackageDetector()

f_idx = 0
saved = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    curr_frame_no = start_frame + f_idx
    if curr_frame_no > FOCUS_END + 20:
        break

    prev_total = detector.total
    prev_large = detector.total_large
    prev_small = detector.total_small

    annotated, events = detector.process_frame(frame)

    if curr_frame_no >= FOCUS_START:
        should_save = (curr_frame_no >= FOCUS_START and curr_frame_no <= FOCUS_END)
        count_changed = detector.total != prev_total

        if should_save or count_changed:
            roi_x, roi_y, roi_w, roi_h = config.ROI
            crop = annotated[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w].copy()

            label = f"F:{curr_frame_no} TOTAL={detector.total} B={detector.total_large} K={detector.total_small}"
            if count_changed:
                label += f" *** +1 {'BESAR' if detector.total_large > prev_large else 'KECIL'} ***"
            cv2.putText(crop, label, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 255) if count_changed else (255, 255, 0), 1)

            fname = f"f{curr_frame_no}{'_COUNT' if count_changed else ''}.jpg"
            cv2.imwrite(os.path.join(OUT_DIR, fname), crop)
            saved += 1

        for ev in events:
            src_sec = curr_frame_no / src_fps
            print(f"[COUNT] F:{curr_frame_no} T:{src_sec/60:.3f}min | {ev['size'].upper()} area={ev['area']:.0f} | TOTAL={detector.total}")

    f_idx += 1

cap.release()
print(f"\nDisimpan {saved} frame ke {OUT_DIR}")

