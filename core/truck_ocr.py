import cv2
import numpy as np
import logging
import re
from config import (
    TRUCK_ROI, TRUCK_CONFIRM_FRAMES, TRUCK_GONE_FRAMES, OCR_CONFIDENCE_MIN
)

logger = logging.getLogger(__name__)

_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        logger.info("Loading EasyOCR model...")
        import easyocr
        _ocr_reader = easyocr.Reader(['en', 'id'], gpu=True, verbose=False)
        logger.info("EasyOCR siap.")
    return _ocr_reader

class TruckDetector:

    def __init__(self):
        self.state = 'EMPTY'
        self.consecutive_detected = 0
        self.consecutive_empty = 0
        self.truck_id = None
        self.truck_raw = None
        self.ocr_done = False

    def is_truck_present_in_frame(self, frame: np.ndarray) -> bool:
        x, y, w, h = TRUCK_ROI
        fh, fw = frame.shape[:2]
        x = max(0, min(x, fw - 1))
        y = max(0, min(y, fh - 1))
        w = min(w, fw - x)
        h = min(h, fh - y)

        zone = frame[y:y+h, x:x+w]
        gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_cnt = cv2.countNonZero(edges)
        return edge_cnt > 2000

    def update(self, frame: np.ndarray) -> dict:
        detected = self.is_truck_present_in_frame(frame)

        if detected:
            self.consecutive_detected += 1
            self.consecutive_empty = 0
        else:
            self.consecutive_empty += 1
            self.consecutive_detected = 0

        if self.state == 'EMPTY':
            if self.consecutive_detected >= TRUCK_CONFIRM_FRAMES:
                self.state = 'PRESENT'
                self.ocr_done = False
                self.truck_id = None
                self.truck_raw = None
                logger.info("[TRUK] Truk terdeteksi masuk → sesi dimulai")
                truck_id, raw = self._run_ocr(frame)
                self.truck_id = truck_id
                self.truck_raw = raw
                return {
                    'event': 'truck_arrived',
                    'truck_id': self.truck_id or 'UNKNOWN',
                    'truck_raw': self.truck_raw or '',
                }

        elif self.state == 'PRESENT':
            if not self.ocr_done:
                truck_id, raw = self._run_ocr(frame)
                if truck_id and truck_id != 'UNKNOWN':
                    self.truck_id = truck_id
                    self.truck_raw = raw
                    self.ocr_done = True
                    logger.info(f"[OCR] Nomor truk terkonfirmasi: {truck_id}")
                    return {
                        'event': 'truck_id_updated',
                        'truck_id': self.truck_id,
                        'truck_raw': self.truck_raw,
                    }

            if self.consecutive_empty >= TRUCK_GONE_FRAMES:
                self.state = 'EMPTY'
                logger.info("[TRUK] Truk pergi → sesi selesai")
                return {'event': 'truck_left'}

        return {'event': None}

    def _run_ocr(self, frame: np.ndarray) -> tuple:
        try:
            x, y, w, h = TRUCK_ROI
            fh, fw = frame.shape[:2]
            x = max(0, min(x, fw - 1))
            y = max(0, min(y, fh - 1))
            w = min(w, fw - x)
            h = min(h, fh - y)

            roi = frame[y:y+h, x:x+w]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            scaled = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

            reader = get_ocr_reader()
            results = reader.readtext(scaled)

            if not results:
                return (None, None)

            texts = []
            for (_, text, conf) in results:
                if conf >= OCR_CONFIDENCE_MIN:
                    texts.append(text.strip())
                    logger.debug(f"[OCR] '{text}' (conf={conf:.2f})")

            raw_text = ' '.join(texts)
            truck_id = self._extract_truck_id(raw_text)
            return (truck_id, raw_text)

        except Exception as e:
            logger.warning(f"[OCR] Gagal: {e}")
            return (None, None)

    def _extract_truck_id(self, raw_text: str) -> str:
        if not raw_text:
            return 'UNKNOWN'

        order_match = re.search(r'ORDER\s*(\d{8,})', raw_text, re.IGNORECASE)
        if order_match:
            return f"ORDER-{order_match.group(1)}"

        number_match = re.findall(r'\b(\d{1,3})\b', raw_text)
        if number_match:
            candidates = [n for n in number_match if 1 <= int(n) <= 999]
            if candidates:
                return candidates[0]

        words = raw_text.split()
        if words:
            return words[0].upper()

        return 'UNKNOWN'

    def get_current_truck_id(self) -> str:
        return self.truck_id or 'UNKNOWN'

    def is_truck_present(self) -> bool:
        return self.state == 'PRESENT'
