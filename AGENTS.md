# AGENTS.md - Aturan Proyek Sistem Monitoring Loading Es Kristal

Tujuan: menghitung kantong es yang dimuat ke truk lewat CCTV secara real-time 24/7 dan memberi alarm pencurian (es keluar ke samping papan luncur / hilang dari pandangan CCTV) dengan false positive serendah mungkin.

## Aturan wajib
- Tulis kode yang bersih, ringkas, dan **tanpa komentar** (`# ...` maupun docstring yang tidak perlu). Keep it clean and simple.
- Hapus file sementara, skrip sekali pakai, dan kode mati yang sudah tidak dipakai. Jaga agar file selalu dikelompokkan rapi di dalam foldernya masing-masing (jangan biarkan file berserakan di root).
- Jangan klaim "akurat" / "sudah bagus" tanpa angka (precision, recall, false alarm per jam) dari video yang TIDAK dipakai untuk training. Pakai skill `ice-detection-accuracy`.
- Jangan tuning threshold/ROI berdasarkan satu video saja lalu menyatakan masalah selesai. Setiap perubahan logika alarm harus disertai test di `tests/` dan dites ulang pada semua video uji.
- Rahasia (API key, token Telegram, password DB, key Supabase) hanya lewat `.env`. Jangan hardcode, jangan cetak ke log/chat, jangan commit `.env`.
- Jangan hapus video utama (`videos/`) atau database (`data/sessions.db`) tanpa izin eksplisit.
- Jangan mengubah dan melatih ulang model pada video yang sama dengan yang dipakai untuk evaluasi.
- Jalankan `python -m pytest tests -q` setelah mengubah `core/engine.py`, `core/detector.py`, `services/security.py`, `server.py`, atau `config.py`.
- Desain Web Dashboard (`server.py` / UI): WAJIB ikuti skill `dashboard-ux-awam` (`.agents/skills/dashboard-ux-awam/SKILL.md`). Hindari tampilan "AI slop" (tema gelap neon/kartu penuh jargon IT); gunakan tata letak terang/bersih kontras tinggi, bahasa Indonesia sehari-hari tanpa istilah teknis AI, ukuran angka besar yang mudah dibaca, pesan error ramah awam, visualisasi interaktif (pemilih kamera, linimasa foto hitungan, modal video bukti, filter tanggal, tooltip `?`), serta aturan anti-salah paham (*not misguided*: pisahkan tegas "Truk Aktif" vs "Total Hari Ini", bedakan 3 status aman/dipantau/pencurian, serta tandai jika kamera/deteksi berhenti).
- Keamanan Web & Stabilitas Program 24/7: WAJIB ikuti skill `ice-production-safety` (`.agents/skills/ice-production-safety/SKILL.md`) setiap kali mengubah web, API, thread, kamera, atau penyimpanan:
  - **Keamanan Web & Login:** Anti-XSS di JS (pakai `textContent`, hindari `innerHTML` untuk data dinamis); blokir akses ketik URL langsung / forced browsing (semua rute data, video bukti, CCTV stream, WebSocket wajib cek sesi login & matikan `/docs` di produksi); aksi ubah-state hanya lewat `POST` + proteksi CSRF; session login pakai hash password (`scrypt`/`bcrypt`), cookie `HttpOnly` + `SameSite`, idle timeout, invalidasi sesi server saat logout, header `Cache-Control: no-store` (anti-Back setelah logout), rate-limit brute-force, serta audit log login/logout/stop kamera; lindungi endpoint admin dengan `Depends(verify_api_key)` / RBAC; validasi `source` video hanya `rtsp://` valid atau file di dalam `videos/` (anti-SSRF & path traversal); masking kredensial RTSP dari UI/log; nonaktifkan simulasi di produksi (`ALLOW_SIMULATION=false`); jangan bocorkan stack trace ke client; jika dibuka di LAN (`0.0.0.0`), wajib HTTPS/proxy + auth.
  - **Anti-Crash & Risiko 24/7:** Gunakan lock thread untuk start/stop engine & `try...finally` untuk rilis `VideoCapture`/sesi; isolasi konfigurasi kamera per instance (jangan mutasi global `config.*` jika 2 kamera berjalan paralel); non-blocking RTSP reader dengan reconnect backoff; batasi ukuran buffer RAM/VRAM (`EvidenceRecorder`, `tracker_history`, antrean offline Telegram/Supabase); gunakan SQLite WAL + timeout lock; tangani gagal tulis disk penuh & JSON state korup tanpa menjatuhkan pipeline hitung utama.
- Komunikasi dengan user dalam Bahasa Indonesia, ringkas.

## Struktur folder & peta kode
- Root:
  - `config.py`: semua parameter (ROI, zona, threshold, `CAMERA_PROFILES`, `auto_select_camera_profile`). Tambah konstanta baru di sini, bukan angka di kode.
  - `server.py`: FastAPI backend + WebSocket + Web Dashboard real-time.
- `core/` (Computer Vision & AI Pipeline):
  - `core/detector.py`: YOLOv8 + ByteTrack + logika penghitungan 3 jalur masuk truk.
  - `core/engine.py`: state machine sesi truk, penghitungan kemasan, dan deteksi/pembatalan anomali ID-agnostik.
  - `core/truck_ocr.py`: deteksi kehadiran truk & OCR plat nomor.
  - `core/stream_manager.py`: pembacaan RTSP/video + tamper guard.
  - `core/evidence_recorder.py`: circular buffer perekam bukti video.
  - `core/hardware.py`: deteksi otomatis profil GPU/CPU.
- `services/` (Database, Cloud, Keamanan & Notifikasi):
  - `services/database.py`: SQLite WAL lokal (`data/sessions.db`).
  - `services/cloud_sync.py`: sinkronisasi background ke Supabase.
  - `services/telegram_notifier.py`: pengiriman notifikasi & video bukti ke Telegram.
  - `services/power_watchdog.py`: pemantau mati listrik / shutdown mendadak.
  - `services/security.py`: verifikasi API key (fail-closed), disk guard, SHA-256 bukti.
- `scripts/` (Utilitas Training & Deployment):
  - `scripts/train_yolo.py`, `scripts/extract_dataset_frames.py`, `scripts/generate_yolo_dataset.py`, `scripts/setup_cabang_baru.py`, `scripts/start_production.bat`, `scripts/setup_autostart_windows.bat`, `scripts/supabase_schema.sql`.
- `videos/`: rekaman video CCTV (`12 Nov.mp4`, `XVR_ch3_main_...mp4`).
- `weights/`: bobot model YOLO (`yolo_ice_best.pt`, `yolov8n.pt`).
- `dataset/yolo_ice/`: dataset gambar & label YOLO (`images/`, `labels/`, `dataset.yaml`).
- `data/`: `sessions.db`, `evidence/`, `snapshots/`, `logs/`, `gt_audit/`.
- `web/`: antarmuka login & web dashboard (`login.html`, `login.js`, `dashboard.html`, `dashboard.js`, `styles.css`).
- `tests/`: unit test (`tests/test_state_machine.py`, `tests/test_web_security.py`).

## Tujuan proyek & aturan domain (dikonfirmasi user, 13 Nov 2026)
Tujuan utama: mendeteksi dan menghitung bungkusan es yang di-loading ke truk secara real-time, dengan mempertimbangkan anomali yang bisa terjadi. Hitungan harus lengkap (recall tinggi) dan alarm harus jarang palsu.

- Semua bungkusan yang akhirnya masuk truk DIHITUNG, apa pun jalurnya: lewat papan, jatuh ke samping lalu dimasukkan lagi, atau dilempar langsung tanpa lewat papan.
- Alarm/Telegram HANYA untuk es yang tidak berakhir di truk: keluar ke samping lalu tidak masuk truk, atau hilang dari pandangan CCTV. Es yang ke samping tapi akhirnya masuk truk = false trigger, jangan alarm.
- Pembatalan alarm tidak boleh bergantung pada track ID yang sama (ID berganti saat es diangkat pekerja). Pakai kedekatan posisi + waktu (`core/engine.py`).
- Area kanan-bawah papan BUKAN zona aman dan bukan "tumpukan resmi". Es di sana tetap dicurigai sampai terbukti masuk truk.
- Ada 2 kamera: CAM 3 (1296x1944, video XVR 22 Okt) dan CAM 10 (1440x1616, `12 Nov.mp4`). Zona per kamera lewat `CAMERA_PROFILE` dan `auto_select_camera_profile` di `config.py`. Kamera baru = tambah profil, jangan ubah angka kamera lain.
- Data: `12 Nov.mp4` seluruhnya dipakai training (user setuju). Karena itu CAM 10 BELUM punya evaluasi; tandai "belum terevaluasi" sampai ada klip CAM 10 baru yang tidak dilatih. CAM 3: frame menit 28.5-37.8 dari `XVR_..200001` sudah dipakai training; evaluasi pakai bagian lain / video `XVR_..192400` dengan ground truth manual.
- Label training harus dikoreksi manual; jangan pseudo-label murni dari keluaran sistem sendiri (melingkar, kantong yang terlewat tetap tak berlabel).
