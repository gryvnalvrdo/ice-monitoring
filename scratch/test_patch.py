import cv2, os, sys
sys.path.insert(0, '.')
import config
from detector import PackageDetector

def test_config(min_top_limit=60):
    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_f = int(28.5 * 60 * src_fps)
    end_f = int(37.8 * 60 * src_fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

    detector = PackageDetector()
    
    # Monkeypatch dead_objects check in process_frame
    orig_process = detector.process_frame
    
    events_log = []
    
    for f in range(start_f, end_f):
        ret, frame = cap.read()
        if not ret: break
        
        # We run the detector logic
        ann, events = detector.process_frame(frame)
        for ev in events:
            src_sec = f / src_fps
            events_log.append({
                'frame': f,
                'time': f"{int(src_sec//60):02d}:{src_sec%60:04.1f}",
                'size': ev['size'],
                'area': ev['area'],
                'total': detector.total,
                'besar': detector.total_large,
                'kecil': detector.total_small
            })
            
    cap.release()
    print(f"\n=== RESULTS (min_top_limit={min_top_limit}) ===")
    print(f"Total counted: {detector.total} (Besar: {detector.total_large}, Kecil: {detector.total_small})")
    print(f"Events around 17-21:")
    for ev in events_log:
        if 17100 <= ev['frame'] <= 18100:
            print(f"  F:{ev['frame']} T:{ev['time']} | {ev['size'].upper()} area={ev['area']:.0f} | Total={ev['total']} (B={ev['besar']} K={ev['kecil']})")

if __name__ == '__main__':
    test_config()

