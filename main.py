import cv2
import numpy as np
import logging
import os
import sys
import time
from datetime import datetime

import config
from database import init_db, create_session, log_package, close_session, update_truck_id
from detector import PackageDetector
from truck_ocr import TruckDetector
from hud_overlay import draw_hud_top_right

os.makedirs(config.LOG_DIR, exist_ok=True)
log_file = os.path.join(
    config.LOG_DIR,
    f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("main")


def draw_hud(frame: np.ndarray, pkg_det: PackageDetector,
             truck_det: TruckDetector, session_id: int,
             session_start: datetime, speed: float = 1.0,
             paused: bool = False, banner: dict = None,
             auto_speed: bool = True):
    fh, fw = frame.shape[:2]
    truck_id = truck_det.get_current_truck_id() or "18"
    is_present = truck_det.is_truck_present()

    if is_present and session_start:
        dur_sec = int((datetime.now() - session_start).total_seconds())
        dur_str = f"{dur_sec//60:02d}:{dur_sec%60:02d}"
    else:
        dur_str = "--:--"

    is_active = (banner and banner.get('frames', 0) > 0)

    frame = draw_hud_top_right(
        frame=frame,
        total=pkg_det.total,
        total_large=pkg_det.total_large,
        total_small=pkg_det.total_small,
        truck_id=truck_id if is_present else "MENUNGGU",
        is_active=is_active,
        cur_speed=speed,
        banner=banner,
        elapsed_str=dur_str
    )

    if paused:
        px1, py1 = (fw // 2) - 220, (fh // 2) - 40
        px2, py2 = (fw // 2) + 220, (fh // 2) + 40
        cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 0), -1)
        cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 255), 3)
        cv2.putText(frame, "=== PAUSED ===", (px1 + 80, py1 + 35),
                    cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(frame, "[SPACE] Lanjut  |  [N] Maju 1 Frame", (px1 + 30, py1 + 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    cv2.rectangle(frame, (0, fh - 35), (fw, fh), (15, 15, 15), -1)
    auto_tag = "AKTIF (Cerdas)" if auto_speed else "MANUAL"
    help_text = f"[SPACE] Pause  |  [A] Auto-Speed: {auto_tag}  |  [-] [+] Speed  |  [D] Debug  |  [Q] Keluar"
    cv2.putText(frame, help_text, (20, fh - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)

    return frame


def print_session_summary(summary: dict):
    print("\n" + "="*55)
    print("       RINGKASAN SESI LOADING SELESAI")
    print("="*55)
    print(f"  Nomor Truk    : {summary.get('truck_id', '-')}")
    print(f"  Kode Order    : {summary.get('truck_raw_ocr', '-')}")
    print(f"  Mulai         : {summary.get('start_time', '-')}")
    print(f"  Selesai       : {summary.get('end_time', '-')}")
    dur = summary.get('duration_sec', 0)
    print(f"  Durasi        : {dur//60} menit {dur%60} detik")
    print(f"  Kemasan Besar : {summary.get('count_large', 0)}")
    print(f"  Kemasan Kecil : {summary.get('count_small', 0)}")
    print(f"  TOTAL         : {summary.get('count_total', 0)}")
    print("="*55 + "\n")


def main():
    logger.info("="*50)
    logger.info("  SISTEM DETEKSI KEMASAN ES KRISTAL DIMULAI")
    logger.info("="*50)
    logger.info(f"Sumber video : {config.VIDEO_SOURCE}")

    init_db()

    is_file_source = not str(config.VIDEO_SOURCE).startswith("rtsp")

    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    if not cap.isOpened():
        logger.error(f"Tidak bisa membuka sumber video: {config.VIDEO_SOURCE}")
        sys.exit(1)

    if not is_file_source and hasattr(cv2, 'CAP_PROP_BUFFERSIZE'):
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    logger.info(f"FPS sumber  : {fps:.1f}")

    start_minute = getattr(config, 'VIDEO_START_MINUTE', 0)
    if is_file_source and start_minute > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start_minute * 60 * 1000)
        logger.info(f"Langsung melompat ke menit ke-{start_minute} (area loading aktif)...")

    pkg_det = PackageDetector()
    truck_det = TruckDetector()

    session_id = None
    session_start = None

    frame_count = 0
    t_start = time.time()

    speed_presets = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 6.0]
    speed_idx = 3
    paused = False
    step_once = False
    banner = {'frames': 0, 'size': '', 'area': 0}
    auto_speed = True
    idle_frames = 0

    is_file_source = not str(config.VIDEO_SOURCE).startswith("rtsp")

    logger.info("Memulai loop deteksi... (tekan Q untuk keluar, SPACE untuk pause, A untuk Auto-Speed)")

    while True:
        if not paused or step_once:
            t_frame_start = time.time()
            ret, frame = cap.read()
            if not ret:
                if is_file_source:
                    logger.info("Video selesai.")
                    if session_id:
                        summary = close_session(session_id)
                        print_session_summary(summary)
                    break
                else:
                    logger.warning("Koneksi kamera live RTSP terputus! Mencoba menyambung ulang dalam 3 detik...")
                    time.sleep(3)
                    cap.release()
                    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
                    if hasattr(cv2, 'CAP_PROP_BUFFERSIZE'):
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    continue

            frame_count += 1
            step_once = False

            if banner['frames'] > 0:
                banner['frames'] -= 1

            truck_event = truck_det.update(frame)

            if truck_event['event'] == 'truck_arrived':
                t_id = truck_event['truck_id']
                t_raw = truck_event['truck_raw']
                session_id = create_session(t_id, t_raw)
                session_start = datetime.now()
                pkg_det.reset_counts()
                logger.info(f"[SESI] Dibuka → ID={session_id}, Truk={t_id}")

            elif truck_event['event'] == 'truck_id_updated' and session_id:
                update_truck_id(session_id,
                                truck_event['truck_id'],
                                truck_event['truck_raw'])

            elif truck_event['event'] == 'truck_left' and session_id:
                summary = close_session(session_id)
                print_session_summary(summary)
                session_id = None
                session_start = None

            pkg_events = []
            if truck_det.is_truck_present() and session_id:
                frame, pkg_events = pkg_det.process_frame(frame)

                for ev in pkg_events:
                    log_package(session_id, ev['size'], ev['area'])
                    banner = {'frames': 20, 'size': ev['size'], 'area': ev['area']}

                    if getattr(config, 'SAVE_SNAPSHOTS', False) and 'crop' in ev and ev['crop'] is not None:
                        snap_dir = os.path.join(config.SNAPSHOT_DIR, f"sesi_{session_id}")
                        os.makedirs(snap_dir, exist_ok=True)
                        snap_path = os.path.join(
                            snap_dir,
                            f"kemasan_{pkg_det.total:04d}_{ev['size']}_{int(ev['area'])}.jpg"
                        )
                        cv2.imwrite(snap_path, ev['crop'])
            else:
                # Mode Pure YOLO: tidak memerlukan update background subtraction konvensional
                pass

            if auto_speed:
                if (banner['frames'] > 0) or len(pkg_events) > 0 or len(getattr(pkg_det.tracker, 'objects', {})) > 0:
                    cur_speed = 1.0
                    idle_frames = 0
                else:
                    idle_frames += 1
                    cur_speed = 4.0 if idle_frames > 15 else 1.0
            else:
                cur_speed = speed_presets[speed_idx]

            frame = draw_hud(frame, pkg_det, truck_det, session_id,
                             session_start, cur_speed, paused, banner, auto_speed)

            last_display_frame = frame.copy()
        else:
            cur_speed = 1.0 if auto_speed else speed_presets[speed_idx]
            frame = draw_hud(last_display_frame.copy(), pkg_det, truck_det,
                             session_id, session_start, cur_speed, paused, banner, auto_speed)

        if config.SHOW_PREVIEW:
            dh, dw = frame.shape[:2]
            scale = min(config.DISPLAY_WIDTH / dw, config.DISPLAY_HEIGHT / dh)
            if scale != 1.0:
                display = cv2.resize(frame, (int(dw*scale), int(dh*scale)))
            else:
                display = frame
            cv2.imshow("Deteksi Kemasan Es Kristal", display)

        if paused:
            wait_time = 30
        elif is_file_source:
            target_delay = (1.0 / (fps * cur_speed))
            work_duration = time.time() - t_frame_start
            wait_time = max(1, int((target_delay - work_duration) * 1000))
        else:
            wait_time = 1

        key = cv2.waitKey(wait_time) & 0xFF

        if key == ord('q') or key == 27:
            logger.info("Program dihentikan oleh user.")
            if session_id:
                summary = close_session(session_id)
                print_session_summary(summary)
            break

        elif key == ord(' '):
            paused = not paused
            logger.info(f"[KONTROL] {'PAUSED' if paused else 'RESUMED'}")

        elif key in (ord('n'), ord('N')):
            if paused:
                step_once = True

        elif key in (ord('a'), ord('A')):
            auto_speed = not auto_speed
            logger.info(f"[KONTROL] Auto-Speed: {'AKTIF (Cerdas)' if auto_speed else 'MANUAL'}")

        elif key in (ord('-'), ord('[')):
            auto_speed = False
            speed_idx = max(0, speed_idx - 1)
            logger.info(f"[KONTROL] Kecepatan Manual: {speed_presets[speed_idx]}x")

        elif key in (ord('+'), ord('='), ord(']')):
            auto_speed = False
            speed_idx = min(len(speed_presets) - 1, speed_idx + 1)
            logger.info(f"[KONTROL] Kecepatan Manual: {speed_presets[speed_idx]}x")

        elif key == ord('d'):
            config.SHOW_CONTOURS = not config.SHOW_CONTOURS
            config.SHOW_ROI_BOX = not config.SHOW_ROI_BOX

    cap.release()
    cv2.destroyAllWindows()

    total_time = time.time() - t_start
    logger.info(f"Total frame diproses : {frame_count}")
    logger.info(f"Total waktu berjalan : {total_time:.1f} detik")
    logger.info("Program selesai.")


if __name__ == "__main__":
    main()
