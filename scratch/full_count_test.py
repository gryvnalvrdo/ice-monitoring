import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import cv2
import time
import config
from engine import IceDetectionEngine
from hardware import hardware

def run_test(duration_minutes=3.0):
    print("=" * 65)
    print("    PENGUJIAN VALIDASI COUNTING & ENGINE PURE YOLO")
    print("=" * 65)
    print(f"Hardware AI : {hardware.hardware_info['device_name']}")
    print(f"Device Mode : {hardware.get_device()} | ImgSz: {hardware.get_imgsz()}p")
    print(f"Sumber Video: {config.VIDEO_SOURCE}")
    print(f"Mulai Menit : {config.VIDEO_START_MINUTE}")
    print(f"Durasi Test : {duration_minutes} menit")
    print("=" * 65)

    engine = IceDetectionEngine(video_source=config.VIDEO_SOURCE, city="Makassar")

    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(config.VIDEO_START_MINUTE * 60 * fps)
    max_frames = int(duration_minutes * 60 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    t0 = time.time()
    f_processed = 0

    print(f"\n[ENGINE] Memulai inferensi real-time {max_frames} frame...")
    while f_processed < max_frames and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        f_processed += 1
        proc_frame, events = engine.process_frame(frame)

        if events:
            for ev in events:
                print(f"  [Frame {start_frame + f_processed}] Es {ev['size'].upper()} #{ev['track_id']} masuk | Conf: {ev.get('conf', 0):.2f}")

        if f_processed % 300 == 0:
            elapsed = time.time() - t0
            cur_fps = f_processed / elapsed
            print(f"  Progress: {f_processed}/{max_frames} frames ({cur_fps:.1f} FPS) | Es Besar: {engine.detector.total_large} | Es Kecil: {engine.detector.total_small}")

    cap.release()
    total_time = time.time() - t0
    avg_fps = f_processed / total_time if total_time > 0 else 0

    print("\n" + "=" * 65)
    print("                 HASIL AKHIR PENGUJIAN")
    print("=" * 65)
    print(f"Total Frame Diproses : {f_processed} frames ({f_processed / fps:.1f} detik rekaman)")
    print(f"Waktu Eksekusi       : {total_time:.2f} detik")
    print(f"Rata-rata FPS        : {avg_fps:.1f} FPS")
    print(f"Nomor Truk Terbaca   : #{engine.current_truck_id or engine.truck_detector.truck_id}")
    print(f"Total Es Besar       : {engine.detector.total_large}")
    print(f"Total Es Kecil       : {engine.detector.total_small}")
    print(f"Grand Total Es       : {engine.detector.total}")
    print(f"Anomali Terdeteksi   : {engine.telemetry['active_anomalies_count']}")
    print(f"Stream Status        : {engine.telemetry['stream_status']}")
    print(f"Tamper Status        : {engine.telemetry['tamper_status']}")
    print("=" * 65)

if __name__ == "__main__":
    run_test(duration_minutes=2.0)
