---
name: dashboard-ux-awam
description: Standar desain Web Dashboard monitoring pabrik yang ramah orang awam / gaptek dan bebas "AI slop". Gunakan setiap kali merancang, mengaudit, atau mengubah tampilan HTML/CSS/JS di server.py atau halaman web lainnya.
---

# Standar Desain Web Dashboard Ramah Orang Awam (Anti-AI-Slop)

Tujuan: siapa pun di pabrik (mandor, admin gudang, pemilik) yang tidak paham istilah IT/AI bisa langsung memahami kondisi loading es dan peringatan dalam **3 detik** sejak membuka layar.

## 1. Larangan Keras ("AI Slop")
- DILARANG memakai gaya klise AI: gradien neon ungu/cyan, kaca buram (*glassmorphism*) berlebihan, animasi berdenyut yang mengganggu, atau kartu kecil bertumpuk penuh angka teknis.
- DILARANG menampilkan jargon teknis ke pengguna awam: jangan tulis `FPS`, `YOLO Conf`, `ByteTrack ID`, `Inference Latency`, `Stream Buffer`, `Active Anomalies`, `Tripwire`, `ROI`, `API Key` mentah tanpa bahasa sehari-hari.
- DILARANG membuat grafik hiasan yang tidak langsung membantu keputusan lapangan.

## 2. Bahasa Sehari-hari yang Jelas
Ganti semua label teknis dengan kalimat yang langsung dipahami operator:
- `Stream Connected / Disconnected` → **Kamera Menyala** / **Kamera Terputus (Periksa Kabel/CCTV)**
- `Truck OCR` → **Plat Nomor Truk**
- `Total Package (Large / Small)` → **Total Es Masuk Truk** (`Es Besar` & `Es Kecil`)
- `Suspected Theft / Anomaly` → **Peringatan Es Keluar Jalur** (jelaskan: *"1 karung dibawa ke samping kanan dan hilang dari kamera pukul 14:05"*)
- `System Standby / Processing` → **Siap Memantau** / **Sedang Menghitung Otomatis**

## 3. Hierarki Visual & Keterbacaan Jarak Jauh
- **Warna Status Berbasis Makna (Maksimal 3 warna utama di latar terang/netral bersih yang kontras):**
  - Hijau = Aman / Terhubung / Normal
  - Kuning/Amber = Sedang Diperiksa (es di samping, menunggu masuk truk)
  - Merah = Bahaya / Alarm Pencurian / Kamera Mati
- **Urutan Layar (Dari paling penting ke detail):**
  1. **Bar Status Atas (1 baris):** Apakah kamera hidup? Sedang memantau kamera mana (`CAM 3` / `CAM 10`)? Kapan pembaruan terakhir?
  2. **Angka Utama Berukuran Besar + Video CCTV Live:** Total kantong masuk truk hari ini & sesi truk aktif (angka besar mudah dibaca dari jarak 1–2 meter) bersanding dengan tampilan CCTV langsung.
  3. **Panel Peringatan & Video Bukti:** Jika ada alarm, tampilkan kronologi singkat (*Apa, Jam Berapa, Kamera Mana*) plus tombol besar **"Putar Video Bukti"**.
  4. **Tabel Riwayat Truk Hari Ini:** Jam mulai, jam selesai, plat truk, jumlah es besar/kecil, status aman/ada peringatan.
- **Keadaan Kosong (*Empty State*) yang Informatif:** Jangan tampilkan kotak kosong atau `"No data"`. Tulis pesan menenangkan, misal: *"Belum ada peringatan hari ini — semua proses loading terpantau aman."*
- **Tombol Aksi yang Aman:** Tombol destruktif/pengubah sistem punya label jelas (*"Mulai Pantau"*, *"Hentikan Sementara"*) dan konfirmasi sederhana bila perlu.
