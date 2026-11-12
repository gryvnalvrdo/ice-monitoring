import cv2
import config
from detector import PureYOLOPackageDetector

def export_yolo_demo(output_video="demo_yolo_pure.mp4", duration_sec=30):
    print("=" * 60)
    print("      EXPORT DEMO VIDEO DETEKSI PURE YOLO")
    print("=" * 60)

    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(config.VIDEO_START_MINUTE * 60 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    det = PureYOLOPackageDetector()

    ret, sample_frame = cap.read()
    if not ret: return
    fh, fw = sample_frame.shape[:2]

    # Resize output ke 720p agar ringan dan bisa ditonton lancar
    out_w, out_h = 720, 1080
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, (out_w, out_h))

    total_frames = int(duration_sec * fps)
    print(f"Mengekspor {total_frames} frame ({duration_sec} detik) ke: {output_video}...")

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    for i in range(total_frames):
        ret, frame = cap.read()
        if not ret: break

        proc_frame, evs = det.process_frame(frame)
        resized = cv2.resize(proc_frame, (out_w, out_h))
        out.write(resized)

        if (i + 1) % 50 == 0:
            print(f"  Frame {i+1}/{total_frames} selesai diproses...")

    cap.release()
    out.release()
    print("=" * 60)
    print(f"Sukses! Video demo Pure YOLO selesai: {output_video}")
    print(f"Total Es Terhitung: Besar={det.total_large}, Kecil={det.total_small}")
    print("=" * 60)

if __name__ == "__main__":
    export_yolo_demo()

