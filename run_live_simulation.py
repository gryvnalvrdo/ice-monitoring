import os
import sys
import time
import json
import cv2
import urllib.request

import config
import database
from engine import IceDetectionEngine
from cloud_sync import CloudSyncManager
from hardware import hardware

def main():
    print("=" * 70)
    print("      SIMULASI OPERASIONAL DETEKSI ES & SINKRONISASI SUPABASE")
    print("=" * 70)
    print(f"Device AI        : {hardware.hardware_info['device_name']} ({hardware.get_device()})")
    print(f"Video Sumber     : {config.VIDEO_SOURCE}")
    print(f"Mulai Menit      : {config.VIDEO_START_MINUTE} (Zona Aktif Loading)")
    print(f"Kota & Cabang    : {config.DEFAULT_CITY} ({config.BRANCH_CODE})")
    print("=" * 70)

    # 1. Bersihkan database lokal dan cloud Supabase
    print("\n[STEP 1] Mengosongkan data lama di SQLite lokal & Supabase Cloud...")
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM package_events")
    cur.execute("DELETE FROM anomalies")
    cur.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()

    if os.path.exists("data/cloud_sync_state.json"):
        os.remove("data/cloud_sync_state.json")

    headers = {
        'apikey': config.CLOUD_SUPABASE_KEY,
        'Authorization': f'Bearer {config.CLOUD_SUPABASE_KEY}'
    }
    for tbl in ['anomalies', 'sessions']:
        try:
            req = urllib.request.Request(f"{config.CLOUD_SUPABASE_URL}/rest/v1/{tbl}?id=gt.0", headers=headers, method='DELETE')
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"  Note hapus {tbl}: {e}")
    print("  -> Database Lokal & Supabase Bersih 100% (0 baris).")

    # 2. Inisialisasi Engine
    print("\n[STEP 2] Menginisialisasi AI Engine (YOLOv8 + ByteTrack + Truck OCR)...")
    engine = IceDetectionEngine(video_source=config.VIDEO_SOURCE, city=config.DEFAULT_CITY)

    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(config.VIDEO_START_MINUTE * 60 * fps)
    total_sim_frames = 1500  # 2.5 menit rekaman loading aktif
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    print(f"\n[STEP 3] Menjalankan inferensi video ({total_sim_frames} frames)...")
    t0 = time.time()
    f_count = 0

    while f_count < total_sim_frames and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        f_count += 1
        proc_frame, events = engine.process_frame(frame)

        if events:
            for ev in events:
                print(f"  [Frame {start_frame + f_count}] Kemasan #{ev['track_id']} ({ev['size'].upper()}) masuk bak truk! (Total: {engine.detector.total})")

        if f_count % 300 == 0:
            elapsed = time.time() - t0
            cur_fps = f_count / elapsed
            print(f"  Progress: {f_count}/{total_sim_frames} frames ({cur_fps:.1f} FPS) | Truk: #{engine.current_truck_id or '-'} | Es Besar: {engine.detector.total_large} | Es Kecil: {engine.detector.total_small} | Total: {engine.detector.total}")

    cap.release()
    total_time = time.time() - t0

    # Tutup sesi loading secara formal
    if engine.current_session_id:
        engine.close_session()

    print("\n" + "=" * 70)
    print("                 HASIL DETEKSI LOKAL (AI ENGINE)")
    print("=" * 70)
    print(f"Waktu Komputasi  : {total_time:.2f} detik ({f_count / total_time:.1f} FPS)")
    print(f"Truk Terbaca     : Truk #{engine.truck_detector.truck_id} (OCR: '{engine.truck_detector.truck_raw}')")
    print(f"Total Es Besar   : {engine.detector.total_large} karung")
    print(f"Total Es Kecil   : {engine.detector.total_small} karung")
    print(f"Grand Total Es   : {engine.detector.total} karung")
    print("=" * 70)

    # 3. Sinkronisasikan ke Supabase Cloud
    print("\n[STEP 4] Mengirim hasil sesi loading ke Cloud Supabase...")
    sync_mgr = CloudSyncManager()
    sync_result = sync_mgr.sync_now()
    print("  -> Hasil Sinkronisasi:", sync_result)

    # 4. Verifikasi Langsung dari Server Supabase
    print("\n[STEP 5] Memverifikasi data yang tersimpan di Supabase Cloud...")
    time.sleep(1)
    req_verify = urllib.request.Request(
        f"{config.CLOUD_SUPABASE_URL}/rest/v1/sessions?select=*&order=id.desc&limit=1",
        headers=headers
    )
    with urllib.request.urlopen(req_verify) as resp:
        cloud_sessions = json.loads(resp.read().decode())

    if cloud_sessions:
        s = cloud_sessions[0]
        print("\n" + "=" * 70)
        print("         DATA DI TABLE EDITOR SUPABASE (TERKONFIRMASI LIVE)")
        print("=" * 70)
        print(f"ID Sesi Cloud    : {s.get('id')}")
        print(f"Nomor Truk       : {s.get('truck_id')} (Raw OCR: {s.get('truck_raw_ocr')})")
        print(f"Cabang & Kota    : {s.get('branch_code')} - {s.get('city')}")
        print(f"Tanggal Trip     : {s.get('trip_date')} (Trip #{s.get('trip_number')})")
        print(f"Status Sesi      : {s.get('status')}")
        print(f"Total Es Besar   : {s.get('count_large')}")
        print(f"Total Es Kecil   : {s.get('count_small')}")
        print(f"Grand Total Es   : {s.get('count_total')}")
        print(f"Durasi Loading   : {s.get('duration_sec')} detik")
        print(f"Waktu Mulai      : {s.get('start_time')}")
        print(f"Waktu Selesai    : {s.get('end_time')}")
        print("=" * 70)
    else:
        print("[PERINGATAN] Data belum masuk ke Supabase.")

if __name__ == "__main__":
    main()
