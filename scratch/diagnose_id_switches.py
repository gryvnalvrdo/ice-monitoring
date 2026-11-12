import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import cv2
import config
from detector import PureYOLOPackageDetector

def test_cooldown():
    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(28.0 * 60 * fps)
    end_frame = int(38.0 * 60 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    det = PureYOLOPackageDetector()
    det.reset_counts()

    raw_events = []
    f_idx = 0
    total_frames = end_frame - start_frame

    while f_idx < total_frames and cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        curr_frame = start_frame + f_idx
        f_idx += 1

        proc_frame, evs = det.process_frame(frame)
        for e in evs:
            raw_events.append((curr_frame, e['track_id'], e['size']))

    cap.release()
    print(f"Total raw events detected: {len(raw_events)}")

    # Cek jarak antar event berturut-turut
    print("\nInterval antar event yang sangat dekat (< 15 frame / 1.5 detik):")
    close_pairs = 0
    filtered_events = []
    last_frame = -999
    for f, tid, sz in raw_events:
        diff = f - last_frame
        if diff < 15:
            close_pairs += 1
            print(f"  Frame {f} (ID #{tid}) berjarak hanya {diff} frame dari frame {last_frame} -> ID switch!")
        else:
            filtered_events.append((f, tid, sz))
        last_frame = f

    print(f"\nTotal duplicate akibat ID switch: {close_pairs}")
    print(f"Total setelah filter cooldown 15 frames: {len(filtered_events)} (Ground Truth: 63)")

if __name__ == "__main__":
    test_cooldown()

