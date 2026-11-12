import cv2
import numpy as np
import config


def draw_hud_top_right(frame: np.ndarray,
                       total: int,
                       total_large: int,
                       total_small: int,
                       truck_id: str = "18",
                       is_active: bool = False,
                       cur_speed: float = 1.0,
                       banner: dict = None,
                       elapsed_str: str = "00:00") -> np.ndarray:
    fh, fw = frame.shape[:2]
    scale = fw / 1296.0

    rx, ry, rw, rh = config.ROI

    bw = int(480 * scale)
    bh = int(360 * scale)
    x1 = int((rx + rw + 20) * scale)
    x1 = min(x1, fw - bw - int(10 * scale))
    x2 = x1 + bw
    y1 = int(ry * scale)
    y2 = y1 + bh

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (18, 18, 22), -1)

    if banner and banner.get('frames', 0) > 0:
        b_size = banner.get('size', 'large')
        border_col = (0, 140, 255) if b_size == 'large' else (0, 230, 255)
        border_thick = max(2, int(3 * scale))
    elif is_active:
        border_col = (0, 255, 120)
        border_thick = max(1, int(2 * scale))
    else:
        border_col = (70, 75, 85)
        border_thick = 1

    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), border_col, border_thick)

    hdr_h = int(46 * scale)
    cv2.rectangle(frame, (x1, y1), (x2, y1 + hdr_h), (30, 32, 40), -1)

    header_title = f"TRUK #{truck_id} | ES KRISTAL"
    cv2.putText(frame, header_title,
                (x1 + int(16 * scale), y1 + int(31 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 0.64 * scale, (255, 255, 255), max(1, int(1.5 * scale)))

    if cur_speed > 1.0:
        spd_text = f"SPEED: {cur_speed:.0f}x"
        spd_color = (0, 180, 255)
    else:
        spd_text = "SPEED: 1.0x"
        spd_color = (0, 255, 100)

    (stw, _), _ = cv2.getTextSize(spd_text, cv2.FONT_HERSHEY_DUPLEX, 0.58 * scale, 1)
    cv2.putText(frame, spd_text,
                (x2 - stw - int(12 * scale), y1 + int(31 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 0.58 * scale, spd_color, max(1, int(1.5 * scale)))

    row1_y = y1 + int(96 * scale)
    cv2.putText(frame, "TOTAL ES", (x1 + int(20 * scale), row1_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72 * scale, (200, 205, 215), max(1, int(1.5 * scale)))

    total_str = f"{total}"
    cv2.putText(frame, total_str, (x1 + int(210 * scale), row1_y + int(8 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 1.45 * scale, (255, 255, 255), max(2, int(2.5 * scale)))

    cv2.putText(frame, "bks", (x1 + int(330 * scale), row1_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, (150, 155, 165), 1)

    div_y = y1 + int(120 * scale)
    cv2.line(frame, (x1 + int(15 * scale), div_y), (x2 - int(15 * scale), div_y), (50, 55, 65), 1)

    box_top = y1 + int(135 * scale)
    box_bot = y1 + int(215 * scale)
    half_w = (bw - int(55 * scale)) // 2

    b_x1 = x1 + int(18 * scale)
    b_x2 = b_x1 + half_w
    cv2.rectangle(frame, (b_x1, box_top), (b_x2, box_bot), (35, 42, 55), -1)
    cv2.rectangle(frame, (b_x1, box_top), (b_x2, box_bot), (0, 140, 255), max(1, int(1.5 * scale)))

    cv2.putText(frame, "BESAR", (b_x1 + int(12 * scale), box_top + int(26 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62 * scale, (0, 160, 255), max(1, int(1.5 * scale)))
    cv2.putText(frame, f"{total_large}", (b_x1 + int(12 * scale), box_bot - int(14 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 1.15 * scale, (255, 255, 255), max(1, int(2 * scale)))
    cv2.putText(frame, "bks", (b_x2 - int(45 * scale), box_bot - int(16 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52 * scale, (170, 175, 185), 1)

    k_x1 = b_x2 + int(16 * scale)
    k_x2 = k_x1 + half_w
    cv2.rectangle(frame, (k_x1, box_top), (k_x2, box_bot), (40, 48, 42), -1)
    cv2.rectangle(frame, (k_x1, box_top), (k_x2, box_bot), (0, 230, 255), max(1, int(1.5 * scale)))

    cv2.putText(frame, "KECIL", (k_x1 + int(12 * scale), box_top + int(26 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62 * scale, (0, 230, 255), max(1, int(1.5 * scale)))
    cv2.putText(frame, f"{total_small}", (k_x1 + int(12 * scale), box_bot - int(14 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 1.15 * scale, (255, 255, 255), max(1, int(2 * scale)))
    cv2.putText(frame, "bks", (k_x2 - int(45 * scale), box_bot - int(16 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52 * scale, (170, 175, 185), 1)

    st_top = y1 + int(230 * scale)
    st_bot = y2 - int(14 * scale)
    cv2.rectangle(frame, (x1 + int(15 * scale), st_top), (x2 - int(15 * scale), st_bot), (25, 28, 35), -1)

    if banner and banner.get('frames', 0) > 0:
        b_size = banner.get('size', 'large')
        b_area = banner.get('area', 0)
        if b_size == 'large':
            notif_text = f"+1 KEMASAN BESAR ({int(b_area):,} px^2)"
            notif_col = (0, 140, 255)
        else:
            notif_text = f"+1 KEMASAN KECIL ({int(b_area):,} px^2)"
            notif_col = (0, 230, 255)
        cv2.rectangle(frame, (x1 + int(15 * scale), st_top), (x2 - int(15 * scale), st_bot), notif_col, 2)
    elif is_active:
        notif_text = "KEMASAN MELUNCUR..."
        notif_col = (0, 255, 120)
    else:
        notif_text = "MENUNGGU KEMASAN..."
        notif_col = (130, 140, 150)

    cv2.putText(frame, notif_text,
                (x1 + int(26 * scale), st_bot - int(15 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 0.64 * scale, notif_col, max(1, int(1.5 * scale)))

    bar_w = int(480 * scale)
    bar_h = int(68 * scale)
    cv2.rectangle(frame, (int(20 * scale), int(20 * scale)),
                  (int(20 * scale) + bar_w, int(20 * scale) + bar_h), (20, 24, 30), -1)
    cv2.rectangle(frame, (int(20 * scale), int(20 * scale)),
                  (int(20 * scale) + bar_w, int(20 * scale) + bar_h), (0, 230, 120), max(1, int(2 * scale)))

    truck_lbl = f"TRUK : {truck_id}"
    cv2.putText(frame, truck_lbl, (int(35 * scale), int(20 * scale) + int(46 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 0.92 * scale, (0, 255, 120), max(2, int(2.5 * scale)))

    time_lbl = f"WAKTU: {elapsed_str}"
    cv2.putText(frame, time_lbl, (int(290 * scale), int(20 * scale) + int(45 * scale)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.70 * scale, (240, 240, 240), max(1, int(1.5 * scale)))

    return frame
