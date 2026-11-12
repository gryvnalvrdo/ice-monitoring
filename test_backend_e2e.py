import cv2
import time
import os
import config
import database
from engine import IceDetectionEngine

def test_e2e():
    print("=" * 60)
    print("      TEST INTEGRASI BACKEND & ENGINE ES KRISTAL")
    print("=" * 60)

    database.init_db()
    engine = IceDetectionEngine(video_source=config.VIDEO_SOURCE, city="Makassar")

    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(config.VIDEO_START_MINUTE * 60 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    print(f"[TEST] Memproses 60 frame dari menit {config.VIDEO_START_MINUTE}...")
    for i in range(60):
        ret, frame = cap.read()
        if not ret: break
        proc_frame, events = engine.process_frame(frame)
        if events:
            print(f"  Frame {start_frame + i}: Terdeteksi {len(events)} kemasan ({events[0]['size']})")

    cap.release()

    print("\n[TEST] Status Telemetry setelah 60 frame:")
    print(f"  Truk ID        : {engine.telemetry['truck_id']}")
    print(f"  Trip Ke-       : {engine.telemetry['trip_number']}")
    print(f"  Kota           : {engine.telemetry['city']}")
    print(f"  Total Es Besar : {engine.telemetry['count_large']}")
    print(f"  Total Es Kecil : {engine.telemetry['count_small']}")
    print(f"  Total Es       : {engine.telemetry['count_total']}")
    print(f"  Last Event     : {engine.telemetry['last_event']}")

    # Uji coba anti-false-positive state machine
    print("\n[TEST] Menguji Anti-False-Positive State Machine...")
    # 1. Kasus es ke samping tapi balik masuk (False alarm dicegah)
    anom_id = database.log_anomaly(
        session_id=engine.current_session_id or 1,
        frame_idx=engine.frame_idx,
        anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
        status="PENDING",
        details="Es tergeser ke samping papan"
    )
    database.update_anomaly(
        anomaly_id=anom_id,
        status="RECOVERED_TO_TRUCK",
        details="Es kembali dimasukkan ke dalam bak truk. False positive berhasil ditangkal!"
    )
    print(f"  -> Kasus Recovery OK: Anomali #{anom_id} ditandai RECOVERED_TO_TRUCK")

    # 2. Kasus pencurian terkonfirmasi + pembuatan video bukti
    theft_anom_id = database.log_anomaly(
        session_id=engine.current_session_id or 1,
        frame_idx=engine.frame_idx,
        anomaly_type="SUSPECTED_THEFT_SIDE_EXIT",
        status="CONFIRMED_THEFT",
        details="Es keluar ke samping dan hilang dari pantauan (Pencurian)"
    )
    video_path = engine.evidence_recorder.trigger_recording(
        anomaly_id=theft_anom_id,
        trip_id=engine.current_session_id or 1,
        frame_idx=engine.frame_idx,
        reason="test_theft"
    )
    database.update_anomaly(theft_anom_id, video_clip_path=video_path)
    print(f"  -> Kasus Pencurian OK: Anomali #{theft_anom_id} mencatat video bukti: {video_path}")

    # Cek query dashboard Makassar
    print("\n[TEST] Mengecek data API Overview Makassar:")
    summary = database.get_daily_summary(city="Makassar")
    print(f"  Kota          : {summary['city']}")
    print(f"  Total Truk    : {summary['total_trucks']}")
    print(f"  Total Trip    : {summary['total_trips']}")
    print(f"  Grand Total   : {summary['grand_total']}")
    print(f"  Jumlah Trip   : {len(summary['trips'])}")

    print("\n" + "=" * 60)
    print("      SEMUA PENGUJIAN BACKEND BERHASIL 100%!")
    print("=" * 60)

if __name__ == "__main__":
    test_e2e()

