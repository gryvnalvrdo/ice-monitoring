import cv2
import os
import argparse
import csv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("extractor")


def extract_frames(source_video: str,
                   output_dir: str = "dataset/extracted_frames",
                   start_min: float = 28.5,
                   end_min: float = 37.8,
                   interval_frames: int = 6,
                   motion_thresh: float = 1000.0,
                   roi: tuple = (420, 1050, 280, 370)):
    """
    Mengekstrak frame dari video rekaman untuk dijadikan dataset training YOLO.
    Fitur:
    - Interval sampling (misal setiap 6 frame = 0.6 detik)
    - Motion filtering di area loading (menghindari duplikasi gambar kosong yang sama)
    - Menyimpan manifest.csv berisi metadata frame
    """
    if not os.path.exists(source_video):
        logger.error(f"Video sumber tidak ditemukan: {source_video}")
        return

    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    cap = cv2.VideoCapture(source_video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_f = int(start_min * 60 * fps)
    end_f = int(end_min * 60 * fps) if end_min > 0 else total_frames
    end_f = min(end_f, total_frames)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    logger.info(f"Mulai ekstraksi: Frame {start_f} s/d {end_f} (Interval: {interval_frames}f, FPS: {fps})")

    prev_roi_gray = None
    extracted_records = []
    f_idx = start_f
    saved_count = 0

    manifest_path = os.path.join(output_dir, "manifest.csv")

    while f_idx < end_f:
        ret, frame = cap.read()
        if not ret:
            break

        # Filter interval
        if (f_idx - start_f) % interval_frames == 0:
            rx, ry, rw, rh = roi
            roi_crop = frame[ry:ry+rh, rx:rx+rw]
            roi_gray = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2GRAY)

            # Cek apakah ada aktivitas/gerakan di area loading
            has_activity = True
            diff_score = 0
            if prev_roi_gray is not None:
                diff = cv2.absdiff(prev_roi_gray, roi_gray)
                diff_score = float(diff.sum() / 1000.0)
                if diff_score < motion_thresh:
                    has_activity = False

            prev_roi_gray = roi_gray

            if has_activity or saved_count == 0:
                saved_count += 1
                img_name = f"frame_{f_idx:06d}.jpg"
                img_path = os.path.join(images_dir, img_name)
                cv2.imwrite(img_path, frame)

                m = (f_idx / fps) / 60
                s = (f_idx / fps) % 60
                time_str = f"{int(m):02d}:{int(s):02d}"

                extracted_records.append({
                    'filename': img_name,
                    'frame_idx': f_idx,
                    'timestamp': time_str,
                    'motion_score': round(diff_score, 1)
                })

                if saved_count % 50 == 0:
                    logger.info(f"Telah mengekstrak {saved_count} frame (Menit {time_str})...")

        f_idx += 1

    cap.release()

    # Tulis manifest
    with open(manifest_path, 'w', newline='', encoding='utf-8') as mf:
        writer = csv.DictWriter(mf, fieldnames=['filename', 'frame_idx', 'timestamp', 'motion_score'])
        writer.writeheader()
        writer.writerows(extracted_records)

    logger.info(f"Selesai! Berhasil mengekstrak {saved_count} gambar ke folder: {images_dir}")
    logger.info(f"Manifest tersimpan di: {manifest_path}")
    return saved_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ekstraktor Frame Dataset CCTV untuk Training YOLO")
    parser.add_argument("--source", type=str, default="XVR_ch3_main_20261022200001_20261022203800.mp4",
                        help="Path ke file video MP4")
    parser.add_argument("--output", type=str, default="dataset/extracted_frames",
                        help="Folder tujuan ekstraksi")
    parser.add_argument("--start-min", type=float, default=28.5,
                        help="Menit mulai (default: 28.5)")
    parser.add_argument("--end-min", type=float, default=37.8,
                        help="Menit selesai (default: 37.8)")
    parser.add_argument("--interval", type=int, default=8,
                        help="Interval frame (default: 8 frame = 0.8 detik)")
    parser.add_argument("--motion-thresh", type=float, default=50.0,
                        help="Threshold deteksi gerakan")
    args = parser.parse_args()

    extract_frames(
        source_video=args.source,
        output_dir=args.output,
        start_min=args.start_min,
        end_min=args.end_min,
        interval_frames=args.interval,
        motion_thresh=args.motion_thresh
    )

