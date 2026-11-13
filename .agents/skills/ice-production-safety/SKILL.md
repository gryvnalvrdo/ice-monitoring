---
name: ice-production-safety
description: Checklist keamanan web, rahasia, pencegahan error/crash, dan keandalan 24/7 untuk sistem monitoring es (XSS, SSRF, auth, RTSP hang, VRAM OOM, SQLite lock, multi-kamera). Gunakan sebelum deploy ke pabrik atau saat mengubah server/security/config/dashboard.
---

# Keamanan Web, Pencegahan Crash & Keandalan Produksi 24/7

## 1. Keamanan Web Dashboard, Login & API
- **Blokir Akses Ketik URL Langsung (Anti-Forced Browsing & Anti-GET Action):**
  - Semua halaman internal, API data (`/api/overview`, `/api/trips`, `/api/anomalies`), video bukti (`/api/evidence/*`), stream CCTV, dan WebSocket (`/ws/telemetry`) WAJIB menolak akses tanpa sesi login yang sah (`401` untuk API/WS atau redirect ke halaman `/login` untuk halaman web). Jangan biarkan file/video bisa diunduh hanya bermodal menebak URL di address bar.
  - Aksi pengubah sistem (start/stop kamera, ubah setting, logout) DILARANG menggunakan method `GET`; wajib `POST` agar tidak bisa dipicu dengan mengetik URL di browser atau lewat tag gambar/link.
  - Matikan halaman dokumentasi API bawaan (`/docs`, `/redoc`, `/openapi.json`) di mode produksi agar daftar endpoint tidak terekspos ke pihak luar.
- **Sistem Login Admin, Session, & Logout yang Aman:**
  - **Password Hashing:** Password admin wajib disimpan dalam bentuk hash kuat ber-salt (`scrypt` / `bcrypt` / `argon2`, bukan teks biasa) di `.env` / DB dan dicocokkan dengan `hmac.compare_digest`.
  - **Cookie Session Aman:** Gunakan token acak `HttpOnly` + `SameSite=Lax`/`Strict` (+ `Secure` jika HTTPS). Jangan pernah taruh session token atau API key di URL (`?token=...`) maupun `localStorage`.
  - **Masa Berlaku & Logout Sejati:** Session wajib punya batas waktu aktif/idle timeout. Tombol **Logout** wajib menghapus sesi di sisi server (*session store* / blacklist) sekaligus memutus koneksi WebSocket/stream live, bukan hanya menghapus cookie di browser.
  - **Anti-Back Button After Logout:** Kirim header `Cache-Control: no-store` pada halaman/API terproteksi agar menekan tombol Back browser setelah logout tidak memunculkan data lama.
  - **Anti-Brute Force Login & Open Redirect:** Batasi percobaan login gagal (mis. maks 5x lalu kunci sementara), serta validasi target redirect pasca-login agar hanya boleh ke path internal `/...`.
  - **Pemisahan Peran (RBAC) & Audit Log:** Pisahkan akun **Operator (Hanya Pantau)** dan **Admin (Kontrol Penuh)**. Setiap login, gagal login, logout, dan aksi mematikan kamera wajib dicatat di log/DB serta mengirim notifikasi Telegram jika kamera dimatikan.
- **CSRF, Security Headers & Anti-XSS:**
  - Setiap `POST/PUT/DELETE` yang memakai cookie session wajib verifikasi **CSRF token** dan `Origin`/`Referer`.
  - Tambahkan header `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, dan `Content-Security-Policy` ketat (anti-clickjacking & anti-script luar).
  - **Anti-XSS di Dashboard:** DILARANG memasukkan data dinamis (`truck_id`, `details`, `last_event`, URL kamera, nama file) ke `innerHTML`. Wajib gunakan `textContent` / DOM API (`createElement`).
- **API Key, Cegah SSRF, Path Traversal & Command Injection:**
  - `REQUIRE_API_KEY=true`, `API_SECRET_KEY` acak kuat di `.env`, `CORS_ORIGINS` spesifik, default `API_HOST=127.0.0.1` (jika LAN `0.0.0.0`, wajib reverse proxy HTTPS).
  - `source` di `/api/engine/start` hanya boleh berupa URL `rtsp://` valid atau path file yang setelah `.resolve()` berada di dalam `videos/`. Tolak `..`, `file://`, atau HTTP ke IP internal.
  - Jika memakai `ffmpeg` / subprocess untuk video bukti, jangan pernah oper input pengguna dengan `shell=True`.
- **Lindungi Kredensial & Pesan Error:**
  - Masking URL RTSP (`rtsp://***@ip...`) sebelum dikirim ke UI, telemetri, API, atau log.
  - Jangan pernah kembalikan stack trace Python atau path internal ke client; tampilkan pesan ramah operator awam di UI.
- **Matikan Endpoint Simulasi di Produksi:** Endpoint seperti `/api/engine/simulate_*` wajib diblokir jika `ALLOW_SIMULATION=false`.
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

## 4. Arsitektur Multi-Cabang Indonesia, Alur Deploy & Kebutuhan Hardware
### Alur Paling Sederhana & Tahan Gangguan (*Edge-to-Cloud*)
1. **Proses Video Tetap di Pabrik Cabang (Lokal):**
   - Jangan mengirim stream mentah CCTV RTSP ke server cloud pusat untuk diproses AI (boros bandwidth internet, macet jika banyak cabang, dan berhenti bila internet mati).
   - Tiap cabang menjalankan 1 PC/Mini-PC lokal yang terhubung LAN langsung ke CCTV/NVR cabang. Semua deteksi kantong es, alarm pencurian, dan penyimpanan awal ke SQLite lokal (`data/sessions.db`) berjalan mandiri 24/7 meski internet pabrik sempat padam.
2. **Sinkronisasi Ringkas ke Cloud Pusat (Tiap 10 Detik):**
   - `services/cloud_sync.py` mengirim hanya ringkasan angka sesi truk dan kejadian anomali (teks ringan beberapa KB, bukan video mentah) ke database pusat **Supabase / PostgreSQL** (`scripts/supabase_schema.sql`), dibedakan per cabang lewat `BRANCH_CODE` (mis. `MKS-01`, `SBY-01`) dan `BRANCH_CITY`.
   - Video bukti pendek (10 detik, lebar maks `960px`) disimpan lokal (`data/evidence/`) dengan auto-hapus berdasarkan umur (`EVIDENCE_RETENTION_DAYS=30`, catatan DB tetap utuh) sekaligus dikirim ke **Telegram** sebagai salinan dan peringatan instan.
3. **Web Dashboard Pusat & Akses Jarak Jauh:**
   - **Portal Rekap Seluruh Cabang (Hosting Pusat):** Cukup jalankan web ringan di VPS/Cloud biasa (tanpa GPU) yang membaca database pusat Supabase untuk menampilkan rekap semua kota/cabang Indonesia dalam satu dashboard (filter cabang, tanggal, ekspor CSV, dan audit kejadian).
   - **Akses Live CCTV Cabang Tertentu:** Jika kantor pusat sesekali ingin melihat live kamera atau mengatur cabang, hubungkan Mini-PC cabang lewat **Cloudflare Tunnel** atau **Tailscale VPN** + HTTPS ke `127.0.0.1:8000` (tanpa buka port router publik / tanpa perlu IP statis di pabrik).
4. **Langkah Tambah Cabang Baru:**
   - Siapkan Mini-PC di cabang + isi `.env` cabang (`BRANCH_CITY`, `BRANCH_CODE` unik, URL RTSP kamera, token Telegram, dan koneksi Supabase pusat yang sama, `ALLOW_SIMULATION=false`, `DISABLE_API_DOCS=true`).
   - Jalankan `python scripts/setup_cabang_baru.py` untuk verifikasi profil & tes koneksi kamera, lalu aktifkan auto-start (`scripts/setup_autostart_windows.bat`).

### Kebutuhan Hardware (Standar untuk Tim Pusat & Pengadaan)
1. **Per Cabang Pabrik (Edge PC / Komputer Lokasi):**
   - **Standar Hemat (1 Kamera, Mode CPU otomatis `core/hardware.py`):** Intel Core i5 Gen 10+ / AMD Ryzen 5 (4–8 physical core), RAM 8–16 GB, SSD 256 GB (sisakan min. 30–50 GB kosong).
   - **Rekomendasi Produksi 24/7 (Stabil untuk 1–2+ Kamera / Akurasi `640p` penuh):** PC Desktop / Mini-PC dengan **GPU NVIDIA min. GTX 1650 / RTX 3050 (VRAM 4–6 GB+)**, CPU Core i5 / Ryzen 5, RAM 16 GB, SSD 256–512 GB.
   - **Perangkat Pendukung Wajib di Pabrik:**
     - **UPS (600–1000 VA)** untuk PC + Switch/NVR agar aman saat listrik kedip dan `power_watchdog` sempat mencatat padam.
     - **Kabel LAN Cat5e/Cat6** antara CCTV/XVR dan Mini-PC (jangan andalkan Wi-Fi untuk stream 24/7).
     - **Kamera CCTV IP / XVR dengan RTSP H.264** menghadap stabil ke papan loading + penerangan cukup saat malam.
     - **Internet Cabang** min. 5–10 Mbps (cukup karena hanya upload teks DB & klip 10 detik saat ada alarm).
2. **Kantor Pusat (Hosting Dashboard Gabungan Semua Cabang):**
   - **Tidak perlu GPU.** Cukup 1 layanan **Database Cloud (Supabase / PostgreSQL)** + 1 **VPS / Cloud Web Hosting ringan (2 vCPU, 2–4 GB RAM)** untuk menayangkan dashboard rekap seluruh cabang Indonesia.
