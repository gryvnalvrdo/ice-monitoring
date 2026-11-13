import cv2
import numpy as np
import logging
import time
from datetime import datetime

import config
import database
from detector import PackageDetector
from truck_ocr import TruckDetector
from evidence_recorder import EvidenceRecorder
from telegram_notifier import TelegramNotifier
from hardware import hardware
from security import security_manager

logger = logging.getLogger(__name__)

class IceDetectionEngine:

    def __init__(self, video_source: str = config.VIDEO_SOURCE,
                 city: str = config.DEFAULT_CITY):
        self.video_source = video_source
        self.city = city
        self.branch_code = config.BRANCH_CODE
        self.detector = PackageDetector()
        self.truck_detector = TruckDetector()
        self.detection_mode = getattr(config, "DETECTION_MODE", "yolo")
        self.evidence_recorder = EvidenceRecorder(
            output_dir=config.EVIDENCE_DIR,
            fps=10.0,
            pre_seconds=config.EVIDENCE_PRE_SECONDS,
            post_seconds=config.EVIDENCE_POST_SECONDS
        )
        self.telegram = TelegramNotifier()

        self.current_session_id = None
        self.current_truck_id = None
        self.current_trip_number = 1
        self.session_start_time = None
        self.is_running = False
        self.frame_idx = 0
        self.fps = 10.0

        self.pending_side_objects = {}

        self.unloaded_objects = set()

        self.telemetry = {
            'is_running': False,
            'fps': 0.0,
            'frame_idx': 0,
            'truck_present': False,
            'truck_id': "-",
            'trip_number': 1,
            'city': self.city,
            'count_large': 0,
            'count_small': 0,
            'count_total': 0,
            'active_anomalies_count': 0,
            'last_event': "Sistem siap",
            'last_event_time': time.strftime("%H:%M:%S"),
            'stream_status': 'IDLE',
            'tamper_status': 'NORMAL',
            'disk_free_gb': 0.0,
            'hardware_device': hardware.get_device(),
            'hardware_name': hardware.hardware_info['device_name'],
        }

    def start_session(self, truck_id: str, truck_raw: str):
        self.current_truck_id = truck_id
        self.session_start_time = datetime.now()
        self.detector.reset_counts()
        self.pending_side_objects.clear()
        self.unloaded_objects.clear()
        self._update_telemetry(active_anomalies_count=0)

        self.current_session_id = database.create_session(
            truck_id=truck_id,
            truck_raw_ocr=truck_raw,
            city=self.city
        )

        session_info = database.get_session_detail(self.current_session_id)
        self.current_trip_number = session_info.get('trip_number', 1)

        self._update_telemetry(
            truck_present=True,
            truck_id=truck_id,
            trip_number=self.current_trip_number,
            last_event=f"Truk {truck_id} masuk (Trip #{self.current_trip_number})"
        )
        logger.info(
            f"[ENGINE] Sesi dimulai: Truk {truck_id} (Trip #{self.current_trip_number}), "
            f"Kota={self.city}, ID={self.current_session_id}"
        )

    def close_session(self, duration_sec: int = None):
        if self.current_session_id:
            summary = database.close_session(self.current_session_id, duration_sec=duration_sec)
            logger.info(f"[ENGINE] Sesi ditutup untuk Truk {self.current_truck_id}")
            self._update_telemetry(
                truck_present=False,
                last_event=f"Truk {self.current_truck_id} selesai loading"
            )
            self.current_session_id = None
            self.current_truck_id = None

    def process_frame(self, frame: np.ndarray) -> tuple:
        self.frame_idx += 1
        fh, fw = frame.shape[:2]

        self.evidence_recorder.add_frame(frame, self.frame_idx)

        truck_event = self.truck_detector.update(frame)
        if truck_event:
            ev_name = truck_event.get('event')
            if ev_name == 'truck_arrived':
                tid = truck_event.get('truck_id', 'UNKNOWN')
                raw = truck_event.get('truck_raw', '')
                self.start_session(truck_id=tid, truck_raw=raw)
            elif ev_name in ('truck_left', 'truck_departed'):
                self.close_session()

        cur_truck = self.truck_detector.get_current_truck_id()
        if cur_truck and cur_truck != self.current_truck_id and self.current_session_id:
            self.current_truck_id = cur_truck
            database.update_truck_id(
                self.current_session_id, cur_truck, self.truck_detector.truck_raw
            )
            self._update_telemetry(truck_id=cur_truck)

        processed_frame, events = self.detector.process_frame(frame)

        for ev in events:
            sz = ev['size']
            ar = ev['area']
            qty = ev.get('quantity', 1)
            is_stk = ev.get('is_stacked', False)

            if self.current_session_id:
                for _ in range(qty):
                    database.log_package(
                        session_id=self.current_session_id,
                        size=sz,
                        area_px=int(ar),
                        frame_idx=self.frame_idx,
                        trajectory="chute",
                        direction="in"
                    )

            last_msg = f"🧊🧊 2 Es Bertumpuk masuk bak truk" if is_stk else f"Es {sz.upper()} masuk bak truk"
            self._update_telemetry(
                count_large=self.detector.total_large,
                count_small=self.detector.total_small,
                count_total=self.detector.total,
                last_event=last_msg
            )

        self._check_side_exit_and_anomalies(frame)

        self._draw_engine_hud(processed_frame)

        return processed_frame, events

    def _check_side_exit_and_anomalies(self, frame: np.ndarray):
        tracked_objects = self.detector.tracker.objects
        frame_w = frame.shape[1] if frame is not None else 1440
        radius = config.SIDE_RECOVERY_RADIUS_FRAC * frame_w
        dup_radius = 0.10 * frame_w
        seen_pending = set()

        for obj_id, obj in list(tracked_objects.items()):
            abs_x, abs_y = obj['centroid']
            is_side_left = (abs_x < config.CHUTE_MIN_X and abs_y > config.TRUCK_ENTRANCE_Y)
            is_side_right = (abs_x > config.CHUTE_MAX_X and abs_y > config.TRUCK_ENTRANCE_Y)
            is_in_truck = (abs_y <= config.TRUCK_ENTRANCE_Y and config.TRUCK_MIN_X <= abs_x <= config.TRUCK_MAX_X)

            if is_side_left or is_side_right:
                side_name = "Kiri" if is_side_left else "Kanan"
                if obj_id not in self.pending_side_objects:

                    near = self._nearest_pending((abs_x, abs_y), dup_radius, exclude=seen_pending)
                    if near is not None:
                        self.pending_side_objects[obj_id] = self.pending_side_objects.pop(near)
                if obj_id in self.pending_side_objects:
                    p = self.pending_side_objects[obj_id]
                    p['last_seen'] = self.frame_idx
                    p['last_pos'] = (abs_x, abs_y)
                    p['on_side'] = True
                    seen_pending.add(obj_id)
                else:
                    anom_id = database.log_anomaly(
                        session_id=self.current_session_id,
                        frame_idx=self.frame_idx,
                        anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
                        status="PENDING",
                        details=f"Es keluar dari papan ke arah samping {side_name}",
                        city=self.city, branch_code=self.branch_code
                    )
                    self.pending_side_objects[obj_id] = {
                        'side_enter_frame': self.frame_idx,
                        'last_seen': self.frame_idx,
                        'last_pos': (abs_x, abs_y),
                        'on_side': True,
                        'anomaly_id': anom_id,
                        'side': side_name,
                        'max_area': obj.get('max_area', 0)
                    }
                    seen_pending.add(obj_id)
                    logger.warning(
                        f"[ZONE] Objek {obj_id} terdeteksi ke samping {side_name}. "
                        f"Membuka jendela pemantauan pemulihan..."
                    )
            else:

                recovered_key = None
                if obj_id in self.pending_side_objects and is_in_truck:
                    recovered_key = obj_id
                else:
                    origin = obj.get('origin', obj['centroid'])
                    cand = self._nearest_pending(origin, radius, exclude=seen_pending,
                                                 must_be_lost=True, obj_id=obj_id)
                    if cand is not None and obj_id not in self.pending_side_objects:
                        recovered_key = cand
                if recovered_key is not None:
                    p_info = self.pending_side_objects[recovered_key]
                    logger.info(
                        f"[RECOVERY] Es dari samping {p_info['side']} kembali ke papan/truk "
                        f"(ID {obj_id}). Alarm dibatalkan, es tetap dihitung."
                    )
                    if p_info['anomaly_id']:
                        database.delete_anomaly(p_info['anomaly_id'])
                    self._update_telemetry(
                        last_event="Es samping kembali masuk bak (False Alarm dihindari)"
                    )
                    del self.pending_side_objects[recovered_key]

        for key, p in self.pending_side_objects.items():
            if key not in seen_pending:
                p['on_side'] = False

        expired = []
        for obj_id, p in self.pending_side_objects.items():
            lost_for = self.frame_idx - p['last_seen']
            dwell = self.frame_idx - p['side_enter_frame']
            if lost_for > config.SIDE_LOST_FRAMES:
                expired.append((obj_id, p, "hilang dari pandangan CCTV"))
            elif p.get('on_side') and dwell > config.SIDE_MAX_DWELL_FRAMES:
                expired.append((obj_id, p, "tertinggal di samping"))
        for obj_id, p, reason in expired:
            self._handle_confirmed_theft(obj_id, p, reason)
            self.pending_side_objects.pop(obj_id, None)

    def _nearest_pending(self, pos, radius, exclude=(), must_be_lost=False,
                         obj_id=None):
        best, best_d = None, radius
        for key, p in self.pending_side_objects.items():
            if key in exclude or key == obj_id:
                continue
            if must_be_lost and p.get('on_side', False) and p['last_seen'] == self.frame_idx:
                continue
            if self.frame_idx - p['last_seen'] > config.SIDE_LOST_FRAMES:
                continue
            d = ((pos[0] - p['last_pos'][0]) ** 2 + (pos[1] - p['last_pos'][1]) ** 2) ** 0.5
            if d <= best_d:
                best, best_d = key, d
        return best

    def _handle_confirmed_theft(self, obj_id: int, p_info: dict,
                                reason_text: str = "hilang dari pandangan CCTV"):
        anom_id = p_info['anomaly_id']
        side = p_info['side']
        logger.error(
            f"🚨 [ALARM PENCURIAN] Objek {obj_id} keluar ke samping {side} "
            f"dan TIDAK MASUK KE TRUK ({reason_text})! Anomali dikonfirmasi."
        )

        trip_id = self.current_session_id or 0
        video_clip_path = self.evidence_recorder.trigger_recording(
            anomaly_id=anom_id,
            trip_id=trip_id,
            frame_idx=self.frame_idx,
            reason="theft_side_exit",
            on_complete=lambda path: self._on_evidence_saved(anom_id, path, trip_id, side)
        )

        if anom_id:
            database.update_anomaly(
                anomaly_id=anom_id,
                status="CONFIRMED_THEFT",
                video_clip_path=video_clip_path,
                details=f"Pencurian/kehilangan es ke samping {side} terkonfirmasi"
            )

        self._update_telemetry(
            active_anomalies_count=self.telemetry['active_anomalies_count'] + 1,
            last_event=f"🚨 Peringatan: Es keluar ke samping {side}!"
        )

    def _on_evidence_saved(self, anomaly_id: int, video_path: str, trip_id: int, side: str):
        logger.info(f"[EVIDENCE] Video bukti siap: {video_path}. Menghitung SHA-256 fingerprint...")
        sha256_hash = security_manager.compute_file_sha256(video_path)
        logger.info(f"[EVIDENCE] SHA-256: {sha256_hash[:16]}...")

        if anomaly_id and sha256_hash:
            database.update_anomaly(
                anomaly_id=anomaly_id,
                details=f"Pencurian/kehilangan es ke samping {side} terkonfirmasi [SHA-256: {sha256_hash[:16]}...]"
            )

        details = {
            'city': self.city,
            'truck_id': self.current_truck_id or "UNKNOWN",
            'trip_number': self.current_trip_number,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'message': (
                f"Es kristal terdeteksi keluar ke samping {side} dan tidak dimasukkan ke dalam truk. "
                f"Potensi pencurian/kehilangan terdeteksi. Bukti video telah dienkripsi (SHA-256)."
            )
        }

        def on_telegram_success():
            if anomaly_id:
                database.update_anomaly(anomaly_id, telegram_sent=True)

        self.telegram.send_alert_async(
            title="DUGAAN PENCURIAN ES TERDETEKSI",
            details=details,
            video_path=video_path,
            on_success=on_telegram_success
        )

    def _on_tampering(self, tamper_type: str, brightness: float):
        logger.error(f"[ENGINE] Sabotase kamera terdeteksi: {tamper_type} (brightness={brightness:.1f})")
        self._update_telemetry(
            tamper_status=tamper_type,
            last_event=f"⚠️ Sabotase Kamera: {tamper_type}"
        )
        if True:
            database.log_anomaly(
                session_id=self.current_session_id,
                frame_idx=self.frame_idx,
                anomaly_type=f"CAMERA_TAMPER_{tamper_type}",
                status="CONFIRMED_THEFT",
                details=f"Kamera terdeteksi disabotase: {tamper_type} (brightness={brightness:.1f})"
            )
        self.telegram.send_alert_async(
            title=f"SABOTASE KAMERA TERDETEKSI: {tamper_type}",
            details={
                'city': self.city,
                'truck_id': self.current_truck_id or "UNKNOWN",
                'trip_number': self.current_trip_number,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'message': f"Kamera monitoring loading disabotase ({tamper_type}, Lux={brightness:.1f}). Periksa lokasi!"
            }
        )

    def _on_stream_disconnect(self):
        logger.warning("[ENGINE] Stream RTSP terputus!")
        self._update_telemetry(stream_status='DISCONNECTED', last_event="⚠️ Stream kamera terputus / CCTV mati!")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        database.log_anomaly(
            session_id=self.current_session_id,
            frame_idx=self.frame_idx,
            anomaly_type="CAMERA_DISCONNECTED",
            status="CONFIRMED_THEFT",
            details="Koneksi CCTV terputus mendadak (mati lampu kamera atau kabel dicabut) saat sistem aktif!",
            city=self.city,
            branch_code=self.branch_code
        )

        self.telegram.send_alert_async(
            title="⚠️ ALIRAN CCTV TERPUTUS / LISTRIK KAMERA PADAM",
            details={
                'city': self.city,
                'branch_code': self.branch_code,
                'truck_id': self.current_truck_id or "-",
                'trip_number': self.current_trip_number,
                'timestamp': now_str,
                'status': 'CCTV OFFLINE (DISCONNECTED)',
                'message': (
                    f"⚠️ PERINGATAN DARURAT CCTV PABRIK:\n"
                    f"Koneksi stream kamera di cabang {self.city} ({self.branch_code}) terputus mendadak pada {now_str}.\n\n"
                    f"• Dugaan Penyebab: Listrik kamera mati, adaptor rusak, atau kabel CCTV dicabut.\n"
                    f"• Status Truk     : #{self.current_truck_id or 'Tidak ada sesi'}\n\n"
                    f"Petugas keamanan harap segera memeriksa kamera di lokasi!"
                )
            }
        )

    def _on_stream_reconnect(self):
        logger.info("[ENGINE] Stream RTSP tersambung kembali.")
        self._update_telemetry(stream_status='CONNECTED', tamper_status='NORMAL', last_event="Stream kamera kembali normal.")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        database.log_anomaly(
            session_id=self.current_session_id,
            frame_idx=self.frame_idx,
            anomaly_type="CAMERA_RECONNECTED",
            status="POWER_RESTORED",
            details="Koneksi CCTV berhasil pulih kembali secara otomatis. Aliran video normal.",
            city=self.city,
            branch_code=self.branch_code
        )

        self.telegram.send_alert_async(
            title="✅ ALIRAN CCTV PULIH / LISTRIK KAMERA NYALA",
            details={
                'city': self.city,
                'branch_code': self.branch_code,
                'truck_id': self.current_truck_id or "-",
                'trip_number': self.current_trip_number,
                'timestamp': now_str,
                'status': 'CCTV ONLINE (RESTORED)',
                'message': (
                    f"✅ CCTV PABRIK KEMBALI NORMAL:\n"
                    f"Koneksi kamera di cabang {self.city} ({self.branch_code}) telah berhasil tersambung kembali pada {now_str}.\n"
                    f"Pengawasan AI dan pencatatan es dilanjutkan otomatis."
                )
            }
        )

    def _update_telemetry(self, **kwargs):
        for k, v in kwargs.items():
            self.telemetry[k] = v
        self.telemetry['last_event_time'] = time.strftime("%H:%M:%S")

    def _draw_engine_hud(self, frame: np.ndarray):
        fh, fw = frame.shape[:2]

        overlay = frame.copy()
        cv2.rectangle(overlay, (20, 20), (430, 215), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        t_id = self.current_truck_id or "MENUNGGU"
        trip_num = self.current_trip_number
        c_large = self.detector.total_large
        c_small = self.detector.total_small
        tot = c_large + c_small

        device_label = hardware.hardware_info['device_name'][:26]
        cv2.putText(frame, f"AI: YOLOv8 | {device_label}", (35, 45),
                    cv2.FONT_HERSHEY_DUPLEX, 0.48, (0, 255, 200), 1)
        cv2.putText(frame, f"KOTA: {self.city.upper()} | TRUK #{t_id}", (35, 70),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(frame, f"TRIP KE-#{trip_num}", (35, 95),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 255, 255), 1)
        cv2.putText(frame, f"TOTAL ES: {tot} (B:{c_large} | K:{c_small})", (35, 120),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 255, 0), 1)

        anom_cnt = self.telemetry['active_anomalies_count']
        alert_col = (0, 0, 255) if anom_cnt > 0 else (180, 180, 180)
        cv2.putText(frame, f"ANOMALI/ALERT: {anom_cnt}", (35, 145),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, alert_col, 1)

        stream_st = self.telemetry.get('stream_status', 'IDLE')
        tamper_st = self.telemetry.get('tamper_status', 'NORMAL')
        stream_col = (0, 255, 0) if stream_st == 'CONNECTED' else (0, 165, 255) if stream_st == 'RECONNECTING' else (0, 0, 255) if stream_st == 'DISCONNECTED' else (180, 180, 180)
        tamper_col = (0, 0, 255) if tamper_st != 'NORMAL' else (0, 255, 0)
        cv2.putText(frame, f"STREAM: {stream_st} | TAMPER: {tamper_st}", (35, 170),
                    cv2.FONT_HERSHEY_DUPLEX, 0.42, stream_col, 1)

        last_ev = self.telemetry.get('last_event', '-')
        cv2.putText(frame, f"LOG: {last_ev[:32]}", (35, 195),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
