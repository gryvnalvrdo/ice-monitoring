# ❄️ Sistem AI Monitoring Loading Es Kristal (Nationwide Multi-Branch)

Sistem *computer vision* dan *edge computing* tingkat produksi (**State of the Art / SOTA**) untuk pemantauan, penghitungan, dan pengamanan muat (*loading*) kantong es kristal ke dalam armada truk melalui kamera CCTV pabrik 24/7.

Dirancang untuk skala **Multi-Cabang di Seluruh Indonesia** dengan arsitektur **Hybrid Edge-to-Cloud** (Mini PC di Pabrik + Supabase Cloud PostgreSQL).

---

## 🌟 Fitur Utama

1. **Pure YOLOv8 Deep Learning + ByteTrack**:
   * Menghitung kantong es secara akurat (*es_besar* dan *es_kecil*) tanpa menggunakan background subtraction kuno (bebas gangguan perubahan cahaya).
   * Kecepatan inferensi mencapai **44+ FPS** pada GPU RTX 3050.
   * **Auto-Hardware Adaptation**: Otomatis fallback ke CPU Mini PC dengan tuning thread pool dan adaptive resolution jika pabrik tidak memiliki GPU.

2. **Deteksi 2 Es Bertumpuk (Stacked Ice)**:
   * Heuristik cerdas mendeteksi tumpukan es ganda ($\text{Area} \ge 55.000\text{ px}$) dan otomatis menghitung **+2 kantong**.

3. **Anti-False-Positive Multi-Zone Surveillance**:
   * Memantau es yang keluar ke samping papan luncur.
   * **Toleransi Pemulihan ($3.5\text{ detik}$)**: Jika es tergeser ke samping namun dikembalikan pekerja ke dalam truk $\to$ status `RECOVERED` (**Alarm dibatalkan**).
   * **Pencurian Terkonfirmasi**: Jika es tidak dimasukkan ke truk atau dibawa menjauh $\to$ status `CONFIRMED_THEFT`, sirine aktif, merekam video 10 detik, dan kirim alert Telegram.

4. **Kriptografi Bukti Video (SHA-256 Tamper-Proof)**:
   * Setiap klip rekaman insiden dihitung hash digital SHA-256 untuk menjamin keaslian bukti hukum.

5. **Ketahanan CCTV & Sabotase Kamera**:
   * Mendeteksi 3 sabotase kamera: *Blackout* (kamera ditutup kain), *Blinded* (disorot laser/senter), dan *Frozen Feed*.
   * Auto-reconnect loop saat CCTV *booting* kembali setelah mati lampu.
   * Riwayat mati lampu/kamera dicatat ke database (`CAMERA_DISCONNECTED` & `CAMERA_RECONNECTED`).

6. **Database Resilient & Cloud Sync (Supabase PostgreSQL)**:
   * **Local Edge**: SQLite dengan mode **WAL (Write-Ahead Logging)** menjamin 0.1ms latency dan anti-korup saat mati lampu mendadak.
   * **Cloud Sync**: Modul background mengunggah data trip dan anomali ke Supabase Cloud via HTTP REST API (bebas limit koneksi simultan multi-cabang).

7. **Wizard Setup Cabang Baru (1-Menit Onboarding)**:
   * Menambahkan cabang baru di kota lain (Surabaya, Medan, Jakarta) hanya butuh menjalankan satu file wizard.

---

## 📁 Struktur Direktori

```text
├── config.py                  # Konfigurasi terpusat & profil cabang
├── detector.py                # Pure YOLOv8 + ByteTrack detector
├── engine.py                  # Core engine: OCR, state machine, counting
├── hardware.py                # Hardware manager (GPU/CPU adaptive profile)
├── stream_manager.py          # Zero-lag RTSP grabber & tamper guard
├── security.py                # SHA-256 hasher, auto-prune disk, API guard
├── cloud_sync.py              # Edge-to-cloud sync ke Supabase
├── telegram_notifier.py       # Pengirim alert Telegram dengan antrean offline
├── database.py                # SQLite WAL database manager
├── server.py                  # FastAPI REST API & WebSocket Real-time Dashboard
│
├── setup_cabang_baru.py       # Wizard interaktif 1-menit untuk cabang baru
├── start_production.bat       # Launcher produksi dengan Auto-Watchdog
├── setup_autostart_windows.bat# Pemasang auto-start Windows saat PC menyala
├── supabase_schema.sql        # Skema SQL tabel cloud Supabase
│
├── weights/
│   └── yolo_ice_best.pt       # Bobot neural network YOLOv8 teroptimasi
└── data/                      # Database lokal, snapshots, evidence clips
```

---

## 🚀 Panduan Menjalankan Sistem

### 1. Instalasi Dependensi
```powershell
pip install -r requirements.txt
```

### 2. Konfigurasi Cabang Baru (Pabrik Baru)
Cukup jalankan wizard interaktif:
```powershell
python setup_cabang_baru.py
```
Masukkan nama kota (contoh: *Makassar* atau *Surabaya*), kode cabang, dan URL RTSP kamera CCTV.

### 3. Menjalankan Dashboard & Deteksi
Cukup klik ganda:
```text
start_production.bat
```
Atau via terminal:
```powershell
python server.py
```
Buka browser di: **`http://localhost:8000`**

### 4. Pemasangan Otomatis di Mini PC Pabrik
Klik kanan file `setup_autostart_windows.bat` lalu pilih **Run as Administrator**. Sistem akan otomatis menyala di background setiap kali komputer dihidupkan (bahkan setelah mati lampu).

---

## ☁️ Integrasi Cloud Database (Supabase)

1. Buat project baru di **[Supabase.com](https://supabase.com)** (Free Tier).
2. Jalankan isi file [`supabase_schema.sql`](supabase_schema.sql) di menu **SQL Editor**.
3. Masukkan `CLOUD_SUPABASE_URL` dan `CLOUD_SUPABASE_KEY` ke `config.py`.
4. Uji koneksi:
   ```powershell
   python test_supabase_connection.py
   ```

---

## 🛡️ Pengujian Otomatis (E2E Tests)
```powershell
# Uji integrasi engine deteksi
python test_backend_e2e.py

# Uji 10 endpoint REST API & proteksi keamanan
python test_server_api.py
```

---
*Dikembangkan dengan standar industri SOTA untuk operasional 24/7 di seluruh pabrik es di Indonesia.*
