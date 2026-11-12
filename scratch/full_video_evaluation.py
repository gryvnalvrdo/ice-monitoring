import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import cv2
import time
import re
import config
from detector import PureYOLOPackageDetector
from hardware import hardware

def parse_ground_truth(gt_file="scratch/gt_audit/events.txt"):
    """Membaca daftar 63 ground truth events."""
    events = []
    if not os.path.exists(gt_file):
        return events
    with open(gt_file, "r") as f:
        for line in f:
            m = re.search(r"Count\s+(\d+)\s+\|\s+Frame\s+(\d+)\s+\(([\d:]+)\)\s+\|\s+([A-Z]+)", line)
            if m:
                events.append({
                    'count_no': int(m.group(1)),
                    'frame_idx': int(m.group(2)),
                    'timestamp': m.group(3),
                    'size': m.group(4).lower()
                })
    return events

def run_full_video_eval():
    print("=" * 70)
    print("    EVALUASI AKURASI PENUH PURE YOLO vs GROUND TRUTH (63 ES)")
    print("=" * 70)

    gt_events = parse_ground_truth()
    print(f"Ground Truth Tercatat : {len(gt_events)} kantong es (dari audit visual)")
    print(f"Hardware AI           : {hardware.hardware_info['device_name']} ({hardware.get_device()})")
    print(f"Sumber Video          : {config.VIDEO_SOURCE}")
    
    # Range aktif: menit 28.0 (frame 16800) s/d menit 38.0 (frame 22800) = 6000 frames
    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(28.0 * 60 * fps)
    end_frame = int(38.0 * 60 * fps)
    total_frames = end_frame - start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    detector = PureYOLOPackageDetector()
    detector.reset_counts()

    detected_counts = []
    t0 = time.time()

    print(f"\n[EVAL] Menjalankan inferensi pada {total_frames} frame (menit 28.0 - 38.0)...")

    f_idx = 0
    while f_idx < total_frames and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        curr_frame = start_frame + f_idx
        f_idx += 1

        proc_frame, events = detector.process_frame(frame)
        for ev in events:
            detected_counts.append({
                'frame_idx': curr_frame,
                'track_id': ev['track_id'],
                'size': ev['size'],
                'conf': ev.get('conf', 0)
            })

        if f_idx % 600 == 0:
            elapsed = time.time() - t0
            cur_fps = f_idx / elapsed
            print(f"  Progress: {f_idx}/{total_frames} frames ({f_idx/fps:.0f}s rekaman) | FPS: {cur_fps:.1f} | Es Terhitung: {detector.total}")

    cap.release()
    total_time = time.time() - t0

    print("\n" + "=" * 70)
    print("                     HASIL EVALUASI AKURASI")
    print("=" * 70)
    print(f"Total Frame Diproses       : {f_idx} frame ({f_idx/fps/60:.1f} menit)")
    print(f"Waktu Komputasi            : {total_time:.1f} detik ({f_idx/total_time:.1f} FPS)")
    print(f"Ground Truth Aktual        : {len(gt_events)} kantong")
    print(f"Deteksi Pure YOLO Model    : {detector.total} kantong (Besar: {detector.total_large}, Kecil: {detector.total_small})")
    
    # Cocokkan setiap ground truth dengan toleransi window +- 30 frame (~3 detik)
    matched_gt = set()
    for det in detected_counts:
        df = det['frame_idx']
        for gt in gt_events:
            if abs(gt['frame_idx'] - df) <= 35:
                matched_gt.add(gt['count_no'])
                break

    recall_pct = (len(matched_gt) / len(gt_events) * 100) if gt_events else 0
    precision_pct = (len(matched_gt) / len(detected_counts) * 100) if detected_counts else 0

    print(f"Ground Truth Terverifikasi : {len(matched_gt)} / {len(gt_events)} ({recall_pct:.1f}%)")
    print(f"Tingkat Presisi Model      : {precision_pct:.1f}%")
    print("=" * 70)

if __name__ == "__main__":
    run_full_video_eval()

