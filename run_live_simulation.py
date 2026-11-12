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
    print("=" * 70, flush=True)
    print("      SIMULASI FULL 1 VIDEO CCTV PABRIK ES (10 MENIT LOADING)", flush=True)
    print("=" * 70, flush=True)
    print(f"Device AI        : {hardware.hardware_info['device_name']} ({hardware.get_device()})", flush=True)
    print(f"Video Sumber     : {config.VIDEO_SOURCE}", flush=True)
    print(f"Mulai Menit      : {config.VIDEO_START_MINUTE} (Awal Truk Masuk & Mulai Muat)", flush=True)
    print(f"Target Durasi    : 10.0 Menit Full Sesi (~6.000 frames)", flush=True)
    print(f"Kota & Cabang    : {config.DEFAULT_CITY} ({config.BRANCH_CODE})", flush=True)
    print("=" * 70, flush=True)

    # 1. Bersihkan database lokal dan cloud Supabase
    print("\n[STEP 1] Mengosongkan data lama di SQLite lokal & Supabase Cloud...", flush=True)
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
            req = urllib.request.Request(
                f"{config.CLOUD_SUPABASE_URL}/rest/v1/{tbl}?id=gt.0",
                headers=headers,
                method='DELETE'
            )
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"  Note hapus {tbl}: {e}", flush=True)
    print("  -> Database Lokal & Supabase Bersih 100% (0 baris).", flush=True)

    # 2. Inisialisasi AI Engine
    print("\n[STEP 2] Menginisialisasi AI Engine (YOLOv8 + ByteTrack + Truck OCR)...", flush=True)
    engine = IceDetectionEngine(video_source=config.VIDEO_SOURCE, city=config.DEFAULT_CITY)

    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    start_frame = int(config.VIDEO_START_MINUTE * 60 * fps)
    total_sim_frames = 6000  # 10 menit full loading sesi (menit 28.5 s/d 38.5)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    print(f"\n[STEP 3] Memproses 1 Video Full Loading ({total_sim_frames} frames)...", flush=True)
    print("  (Memerlukan waktu ~1.5 - 2 menit pada GPU NVIDIA RTX 3050...)\n", flush=True)
    t0 = time.time()
    f_count = 0

    while f_count < total_sim_frames and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        f_count += 1
        proc_frame, events = engine.process_frame(frame)

        if f_count % 500 == 0 or f_count == total_sim_frames:
            elapsed = time.time() - t0
            cur_fps = f_count / elapsed
            est_left = (total_sim_frames - f_count) / cur_fps if cur_fps > 0 else 0
            print(
                f"  Frame {f_count}/{total_sim_frames} ({cur_fps:.1f} FPS, sisa {est_left:.0f}s) | "
                f"Truk: #{engine.current_truck_id or engine.truck_detector.truck_id or '-'} | "
                f"Es Besar: {engine.detector.total_large} | "
                f"Es Kecil: {engine.detector.total_small} | "
                f"Total: {engine.detector.total}",
                flush=True
            )

    cap.release()
    total_time = time.time() - t0
    recording_duration_sec = int(f_count / fps)

    # Tutup sesi loading secara formal
    if engine.current_session_id:
        engine.close_session(duration_sec=recording_duration_sec)

    print("\n" + "=" * 70, flush=True)
    print("                 HASIL DETEKSI LOKAL (AI ENGINE)", flush=True)
    print("=" * 70, flush=True)
    print(f"Durasi CCTV Asli : {recording_duration_sec // 60} menit {recording_duration_sec % 60} detik", flush=True)
    print(f"Waktu Komputasi  : {total_time:.2f} detik ({f_count / total_time:.1f} FPS)", flush=True)
    print(f"Nomor Truk OCR   : Truk #{engine.truck_detector.truck_id} (Raw OCR: '{engine.truck_detector.truck_raw}')", flush=True)
    print(f"Total Es Besar   : {engine.detector.total_large} karung", flush=True)
    print(f"Total Es Kecil   : {engine.detector.total_small} karung", flush=True)
    print(f"Grand Total Es   : {engine.detector.total} karung", flush=True)
    print("=" * 70, flush=True)

    # 3. Sinkronisasikan ke Supabase Cloud
    print("\n[STEP 4] Mengirim hasil sesi loading ke Cloud Supabase...", flush=True)
    sync_mgr = CloudSyncManager()
    sync_result = sync_mgr.sync_now()
    print("  -> Hasil Sinkronisasi:", sync_result, flush=True)

    # 4. Verifikasi Langsung dari Server Supabase
    print("\n[STEP 5] Memverifikasi data yang tersimpan di Supabase Cloud...", flush=True)
    time.sleep(1)
    req_verify = urllib.request.Request(
        f"{config.CLOUD_SUPABASE_URL}/rest/v1/sessions?select=*&order=id.desc&limit=1",
        headers=headers
    )
    with urllib.request.urlopen(req_verify) as resp:
        cloud_sessions = json.loads(resp.read().decode())

    if cloud_sessions:
        s = cloud_sessions[0]
        print("\n" + "=" * 70, flush=True)
        print("         DATA DI TABLE EDITOR SUPABASE (TERKONFIRMASI LIVE)", flush=True)
        print("=" * 70, flush=True)
        print(f"ID Sesi Cloud    : {s.get('id')}", flush=True)
        print(f"Nomor Truk       : {s.get('truck_id')} (Raw OCR: {s.get('truck_raw_ocr')})", flush=True)
        print(f"Cabang & Kota    : {s.get('branch_code')} - {s.get('city')}", flush=True)
        print(f"Tanggal Trip     : {s.get('trip_date')} (Trip #{s.get('trip_number')})", flush=True)
        print(f"Status Sesi      : {s.get('status')}", flush=True)
        print(f"Total Es Besar   : {s.get('count_large')}", flush=True)
        print(f"Total Es Kecil   : {s.get('count_small')}", flush=True)
        print(f"Grand Total Es   : {s.get('count_total')}", flush=True)
        print(f"Durasi Loading   : {s.get('duration_sec') // 60} menit {s.get('duration_sec') % 60} detik ({s.get('duration_sec')}s)", flush=True)
        print(f"Waktu Mulai      : {s.get('start_time')}", flush=True)
        print(f"Waktu Selesai    : {s.get('end_time')}", flush=True)
        print("=" * 70, flush=True)
    else:
        print("[PERINGATAN] Data belum masuk ke Supabase.", flush=True)

if __name__ == "__main__":
    main()
