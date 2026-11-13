import cv2
import os
import time
import threading
from collections import deque
import logging

logger = logging.getLogger(__name__)

class EvidenceRecorder:

    def __init__(self, output_dir: str = "data/evidence",
                 fps: float = 10.0,
                 pre_seconds: float = 5.0,
                 post_seconds: float = 5.0,
                 max_width: int = 960):
        self.output_dir = output_dir
        self.fps = fps
        self.max_width = max_width
        self.pre_frames_count = int(pre_seconds * fps)
        self.post_frames_count = int(post_seconds * fps)
        self.ring_buffer = deque(maxlen=self.pre_frames_count)
        self.active_recordings = []
        self._lock = threading.Lock()
        os.makedirs(self.output_dir, exist_ok=True)

    def _prep_frame(self, frame):
        fh, fw = frame.shape[:2]
        if self.max_width and fw > self.max_width:
            scale = self.max_width / float(fw)
            return cv2.resize(frame, (self.max_width, max(1, int(fh * scale))), interpolation=cv2.INTER_AREA)
        return frame.copy()

    def add_frame(self, frame, frame_idx: int):
        small = self._prep_frame(frame)
        with self._lock:

            self.ring_buffer.append((frame_idx, small))

            remaining_recordings = []
            for rec in self.active_recordings:
                rec['frames'].append(small.copy())
                rec['remaining_post_frames'] -= 1
                if rec['remaining_post_frames'] <= 0:

                    threading.Thread(
                        target=self._save_video,
                        args=(rec['filename'], rec['frames'], rec['callback']),
                        daemon=True
                    ).start()
                else:
                    remaining_recordings.append(rec)
            self.active_recordings = remaining_recordings

    def trigger_recording(self, anomaly_id: int, trip_id: int, frame_idx: int,
                          reason: str = "theft", on_complete=None) -> str:
        with self._lock:
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(
                self.output_dir,
                f"anomali_trip{trip_id}_anom{anomaly_id}_{timestamp_str}.mp4"
            )

            pre_frames = [f[1].copy() for f in self.ring_buffer]

            rec_job = {
                'anomaly_id': anomaly_id,
                'filename': filename,
                'frames': pre_frames,
                'remaining_post_frames': self.post_frames_count,
                'callback': on_complete
            }
            self.active_recordings.append(rec_job)
            logger.info(
                f"[RECORDER] Merekam bukti video: {filename} "
                f"(Pre={len(pre_frames)}f, Post={self.post_frames_count}f)"
            )
            return filename

    def _save_video(self, output_path: str, frames: list, callback=None):
        if not frames:
            return

        try:
            h, w = frames[0].shape[:2]

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, self.fps, (w, h))

            for f in frames:

                marked = f.copy()
                cv2.putText(
                    marked, "[BUKTI ANOMALI ES]", (20, 40),
                    cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 0, 255), 2
                )
                out.write(marked)

            out.release()
            logger.info(f"[RECORDER] File video bukti berhasil disimpan: {output_path}")

            if callback:
                callback(output_path)
        except Exception as e:
            logger.error(f"[RECORDER] Gagal menyimpan video bukti: {e}")
