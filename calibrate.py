import cv2
import numpy as np
import sys
import re

VIDEO_SOURCE = "XVR_ch3_main_20261022200001_20261022203800.mp4"
SEEK_TO_SEC = 1800
DISPLAY_W = 960
DISPLAY_H = 720

roi = [0, 0, 0, 0]
tripwire_y = 0
size_threshold = 8000
drawing = False
drag_start = None
frame_orig = None
scale = 1.0
cap = None
fps = 25.0


def display_to_frame(dx, dy):
    return int(dx / scale), int(dy / scale)


def frame_to_display(fx, fy):
    return int(fx * scale), int(fy * scale)


def mouse_callback(event, dx, dy, flags, param):
    global roi, drawing, drag_start, tripwire_y

    fx, fy = display_to_frame(dx, dy)

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        drag_start = (fx, fy)

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing and drag_start and frame_orig is not None:
            tmp = make_display(frame_orig)
            sx, sy = frame_to_display(*drag_start)
            cv2.rectangle(tmp, (sx, sy), (dx, dy), (0, 255, 255), 2)
            cv2.imshow("Calibration", tmp)

    elif event == cv2.EVENT_LBUTTONUP:
        if drawing and drag_start:
            drawing = False
            x1 = min(drag_start[0], fx)
            y1 = min(drag_start[1], fy)
            x2 = max(drag_start[0], fx)
            y2 = max(drag_start[1], fy)
            if x2 - x1 > 20 and y2 - y1 > 20:
                roi[0], roi[1] = x1, y1
                roi[2] = x2 - x1
                roi[3] = y2 - y1
                tripwire_y = roi[3] // 2
                print(f"[ROI] x={x1} y={y1} w={roi[2]} h={roi[3]}")
            drag_start = None


def make_display(frame: np.ndarray) -> np.ndarray:
    global scale
    fh, fw = frame.shape[:2]
    scale = min(DISPLAY_W / fw, DISPLAY_H / fh)
    disp_w = int(fw * scale)
    disp_h = int(fh * scale)
    disp = cv2.resize(frame.copy(), (disp_w, disp_h), interpolation=cv2.INTER_LINEAR)

    draw_overlay(disp)
    return disp


def draw_overlay(disp: np.ndarray):
    rx, ry, rw, rh = roi
    drx, dry = frame_to_display(rx, ry)
    drx2, dry2 = frame_to_display(rx + rw, ry + rh)

    if rw > 0 and rh > 0:
        cv2.rectangle(disp, (drx, dry), (drx2, dry2), (0, 255, 255), 2)

    tw_y_frame = ry + tripwire_y
    tw_y_display = frame_to_display(0, tw_y_frame)[1]
    cv2.line(disp, (drx, tw_y_display), (drx2, tw_y_display), (0, 255, 0), 2)
    cv2.putText(disp, f"TRIPWIRE y={tripwire_y}", (drx + 5, tw_y_display - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

    info_lines = [
        f"ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}",
        f"Tripwire Y (rel ROI): {tripwire_y}",
        f"Size threshold: {size_threshold} px2",
        "",
        "DRAG MOUSE : Set area ROI",
        "W / S      : Geser tripwire naik / turun",
        "+ / -      : Ubah threshold besar/kecil",
        "SPACE      : Maju 1 detik  |  B: Mundur 1 detik",
        "R          : Reset ROI",
        "ENTER      : Simpan & keluar",
        "Q / ESC    : Keluar tanpa simpan",
    ]
    panel_h = len(info_lines) * 20 + 14
    overlay = disp.copy()
    cv2.rectangle(overlay, (0, 0), (420, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, disp, 0.4, 0, disp)
    for i, line in enumerate(info_lines):
        cv2.putText(disp, line, (8, 18 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                    (200, 255, 200) if i < 3 else (180, 180, 180),
                    1, cv2.LINE_AA)


def seek_and_read(seconds: float):
    global frame_orig
    cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ret, frame = cap.read()
    if ret:
        frame_orig = frame.copy()
    return ret


def save_config():
    config_path = "config.py"
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    rx, ry, rw, rh = roi
    if rw <= 0 or rh <= 0:
        print("ROI belum di-set! Keluar tanpa menyimpan.")
        return

    content = re.sub(
        r'^ROI\s*=\s*\(.*?\)',
        f"ROI = ({rx}, {ry}, {rw}, {rh})",
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^TRIPWIRE_Y\s*=\s*\d+',
        f"TRIPWIRE_Y = {tripwire_y}",
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^SIZE_THRESHOLD_AREA\s*=\s*\d+',
        f"SIZE_THRESHOLD_AREA = {size_threshold}",
        content, flags=re.MULTILINE
    )

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\nKonfigurasi berhasil disimpan ke config.py:")
    print(f"   ROI             = ({rx}, {ry}, {rw}, {rh})")
    print(f"   TRIPWIRE_Y      = {tripwire_y}")
    print(f"   SIZE_THRESHOLD  = {size_threshold}\n")


def main():
    global cap, fps, roi, tripwire_y, size_threshold, frame_orig

    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"Tidak bisa buka video: {VIDEO_SOURCE}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_sec = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    cur_sec = SEEK_TO_SEC

    print("\n=== MODE KALIBRASI ===")
    print(f"Video  : {VIDEO_SOURCE}")
    print(f"Durasi : {int(total_sec//60)}m {int(total_sec%60)}s")
    print(f"Mulai  : {int(cur_sec//60)}m {int(cur_sec%60)}s\n")

    seek_and_read(cur_sec)

    cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Calibration", DISPLAY_W, DISPLAY_H)
    cv2.setMouseCallback("Calibration", mouse_callback)

    while True:
        if frame_orig is not None:
            disp = make_display(frame_orig)
            cv2.imshow("Calibration", disp)

        key = cv2.waitKey(30) & 0xFF

        if key in (ord('q'), 27):
            print("Keluar tanpa menyimpan.")
            break

        elif key == 13:
            save_config()
            break

        elif key in (ord('w'), 82):
            tripwire_y = max(5, tripwire_y - 5)
            print(f"Tripwire Y = {tripwire_y}")

        elif key in (ord('s'), 84):
            tripwire_y = min(roi[3] - 5 if roi[3] > 0 else 500, tripwire_y + 5)
            print(f"Tripwire Y = {tripwire_y}")

        elif key in (ord('+'), ord('=')):
            size_threshold += 500
            print(f"Size threshold = {size_threshold}")

        elif key == ord('-'):
            size_threshold = max(500, size_threshold - 500)
            print(f"Size threshold = {size_threshold}")

        elif key == ord('r'):
            roi = [0, 0, 0, 0]
            tripwire_y = 0
            print("ROI direset.")

        elif key == 32:
            cur_sec = min(cur_sec + 1, total_sec - 2)
            seek_and_read(cur_sec)
            print(f"Posisi: {int(cur_sec//60)}m {int(cur_sec%60)}s")

        elif key in (ord('b'), ord('B')):
            cur_sec = max(0, cur_sec - 1)
            seek_and_read(cur_sec)
            print(f"Posisi: {int(cur_sec//60)}m {int(cur_sec%60)}s")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
