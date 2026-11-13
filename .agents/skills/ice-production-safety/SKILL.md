---
name: ice-production-safety
description: Checklist keamanan web, rahasia, pencegahan error/crash, dan keandalan 24/7 untuk sistem monitoring es (XSS, SSRF, auth, RTSP hang, VRAM OOM, SQLite lock, multi-kamera). Gunakan sebelum deploy ke pabrik atau saat mengubah server/security/config/dashboard.
---

# Keamanan Web, Pencegahan Crash & Keandalan Produksi 24/7

## 1. Keamanan Web Dashboard & API
- **Anti-XSS di Dashboard:** DILARANG memasukkan data dinamis (`truck_id`, `details`, `last_event`, URL kamera, nama file) ke `innerHTML`. Wajib gunakan `textContent` / DOM API (`createElement`) agar tidak ada injeksi skrip dari input/DB.
- **Autentikasi & Eksposur Jaringan:**
  - `REQUIRE_API_KEY=true`, `API_SECRET_KEY` acak kuat di `.env`, `CORS_ORIGINS` spesifik.
  - Default `API_HOST=127.0.0.1`. Jika perlu diakses lewat LAN/internet (`0.0.0.0`), wajib pasang reverse proxy HTTPS + autentikasi untuk feed kamera, bukti video (`/api/evidence`), riwayat (`/api/trips`, `/api/anomalies`), dan `/ws/telemetry`.
  - Pisahkan mode **Pantau (Read-Only)** vs **Kontrol Admin**; semua endpoint POST/ubah state wajib `Depends(verify_api_key)` + rate limit (termasuk rate limit percobaan API key salah).
- **Cegah SSRF & Path Traversal pada Input Sumber Video:**
  - `source` di `/api/engine/start` hanya boleh berupa URL `rtsp://` yang valid atau path file yang setelah `.resolve()` berada di dalam folder `videos/`. Tolak `..`, skema `file://`, atau URL HTTP ke IP internal metadata/layanan lokal.
- **Lindungi Kredensial & Pesan Error:**
  - RTSP URL sering berisi username & password (`rtsp://user:pass@ip...`). WAJIB di-masking (`rtsp://***@ip...`) sebelum dikirim ke UI, telemetri, API response, atau file log.
  - Jangan pernah kembalikan stack trace Python atau path internal server ke response HTTP; tampilkan pesan ramah operator awam di UI dan simpan detail teknis hanya di log lokal.
- **Matikan Endpoint Simulasi di Produksi:** Endpoint seperti `/api/engine/simulate_*` wajib diblokir jika `ALLOW_SIMULATION=false` agar tidak memicu alarm Telegram palsu atau mengotori database.
- **Integritas Bukti & Rahasia:** `.env` tidak boleh ter-commit. Hash SHA-256 bukti video (`data/evidence/`) disinkronkan ke cloud agar tidak bisa dimanipulasi lokal.

## 2. Pencegahan Error & Crash (Program Stability 24/7)
- **Isolasi Konfigurasi Multi-Kamera:** Jika menjalankan `CAM 3` dan `CAM 10` bersamaan dalam satu proses, JANGAN mutasi variabel global `config.*` (`auto_select_camera_profile`). Setiap instance kamera harus memegang objek konfigurasi/profilnya sendiri agar koordinat zona kedua kamera tidak saling menimpa.
- **Thread Safety & Resource Cleanup:**
  - Gunakan `threading.Lock()` saat start/stop engine agar tidak terjadi race condition / double thread.
  - Bungkus worker loop video/RTSP dengan `try ... finally` sehingga `cap.release()`, penutupan sesi DB, dan reset flag `is_engine_active` selalu berjalan meski terjadi exception.
- **RTSP Putus / Hang Permanen:** `cv2.VideoCapture.read()` bisa membeku saat kabel CCTV putus atau NVR restart. Wajib baca frame di thread manager terpisah (`core/stream_manager.py`) dengan timeout + auto-reconnect *exponential backoff* dan bersihkan buffer frame lama agar tidak terjadi delay menumpuk.
- **Memori & VRAM GPU (4GB):** Batasi ukuran buffer rekaman (`EvidenceRecorder` `maxlen`), bersihkan dictionary history tracking (`tracker_history`, `last_seen_frame`, `counted_at_frame`) secara berkala, dan cegah penumpukan tensor PyTorch di GPU.
- **SQLite Lock & Disk Penuh:** Gunakan timeout koneksi + WAL mode pada `services/database.py`. Jika disk penuh atau gagal menulis snapshot/bukti video (`IOError`/`OSError`), catat error di log tanpa menjatuhkan thread deteksi utama. Auto-prune disk harus berjalan sebelum kapasitas mencapai batas kritis (`MAX_DISK_USAGE_PERCENT`).
- **Kegagalan Jaringan (Telegram / Supabase):** Semua panggilan HTTP eksternal wajib memiliki timeout pendek (`<= 10 detik`), berjalan di background thread/queue dengan kapasitas antrean maksimum agar tidak memenuhi RAM saat internet pabrik mati seharian.
- **Rollover Pergantian Hari (`00:00`) & Mati Listrik:** Pastikan sesi truk yang melintasi tengah malam tetap tertutup rapi dan `power_watchdog` mencatat pemulihan tanpa crash bila file state korup (fallback aman bila JSON korup).

## 3. Uji Sebelum Deploy ke Pabrik
- `python -m pytest tests -q` wajib lulus semua.
- Uji skenario kegagalan: CCTV dicabut & dicolok ulang, internet dimatikan 15 menit lalu nyala, disk disimulasikan penuh, dan API dipanggil tanpa/salah API key.
- Uji soak minimal 72 jam memantau RAM, VRAM, FPS, thread count, dan stabilitas koneksi RTSP.
