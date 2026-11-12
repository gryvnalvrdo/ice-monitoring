import os
import sys
import json
import time

def setup_wizard():
    print("=" * 70)
    print("   🏢 WIZARD SETUP CABANG BARU - SISTEM MONITORING ES KRISTAL")
    print("   (Mendukung Multi-Cabang Seluruh Indonesia dengan 1 Database Cloud)")
    print("=" * 70)
    print("Panduan: Anda hanya perlu menjawab 3 pertanyaan singkat di bawah ini.")
    print("Pengaturan akan otomatis disimpan dan terhubung ke Database Pusat.")
    print("=" * 70)

    # 1. Input Kota
    print("\n[1/3] IDENTITAS LOKASI")
    city_input = input("-> Masukkan Nama Kota Cabang (Contoh: Surabaya, Medan, Jakarta, Makassar): ").strip()
    if not city_input:
        city_input = "Makassar"

    # 2. Input Kode Cabang
    suggested_code = city_input[:3].upper() + "-01"
    code_input = input(f"-> Masukkan Kode Unik Cabang [Default: {suggested_code}]: ").strip()
    if not code_input:
        code_input = suggested_code

    # 3. Input Sumber Video / RTSP Kamera
    print("\n[2/3] KONEKSI KAMERA CCTV CABANG")
    print("Contoh RTSP: rtsp://admin:pass123@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0")
    print("(Atau tekan ENTER untuk menggunakan video pengujian lokal)")
    rtsp_input = input("-> Masukkan URL RTSP Kamera CCTV Cabang: ").strip()
    if not rtsp_input:
        rtsp_input = "XVR_ch3_main_20261022200001_20261022203800.mp4"

    # Simpan ke data/branch_profile.json
    profile = {
        "branch_city": city_input,
        "branch_code": code_input,
        "video_source": rtsp_input,
        "configured_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    os.makedirs("data", exist_ok=True)
    profile_path = "data/branch_profile.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"\n[SUKSES] Profil cabang berhasil disimpan ke: {profile_path}")
    print(f"  * Kota   : {city_input}")
    print(f"  * Kode   : {code_input}")
    print(f"  * Sumber : {rtsp_input}")

    # Tes koneksi kamera
    print("\n[3/3] VERIFIKASI SISTEM")
    print("-> Menguji koneksi sumber video/kamera...")
    import cv2
    cap = cv2.VideoCapture(rtsp_input)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            fh, fw = frame.shape[:2]
            print(f"   ✅ Kamera TERHUBUNG! Resolusi: {fw}x{fh} px")
        else:
            print("   ⚠️ Peringatan: Kamera terdeteksi tapi belum mengirim frame gambar.")
        cap.release()
    else:
        print("   ❌ Peringatan: Gagal membuka stream kamera. Periksa IP, password, atau jaringan LAN cabang.")

    # Verifikasi Cloud Database Supabase
    print("-> Menguji koneksi Cloud Database Pusat (Supabase)...")
    try:
        from test_supabase_connection import test_supabase
        test_supabase()
    except Exception as e:
        print(f"   (Pemeriksaan cloud: {e})")

    print("\n" + "=" * 70)
    print(f"  🎉 SETUP CABANG '{city_input.upper()} ({code_input})' SELESAI!")
    print("=" * 70)
    print("Untuk menjalankan sistem di cabang ini:")
    print("  1. Cukup klik ganda file: start_production.bat")
    print("  2. Atau pasang auto-start dengan klik kanan 'setup_autostart_windows.bat' -> Run as Administrator")
    print("=" * 70)

if __name__ == "__main__":
    setup_wizard()

