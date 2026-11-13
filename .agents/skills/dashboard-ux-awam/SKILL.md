---
name: dashboard-ux-awam
description: Standar desain Web Dashboard monitoring pabrik yang ramah orang awam / gaptek, interaktif, akurat secara visual (anti-misleading), dan bebas "AI slop". Gunakan setiap kali merancang, mengaudit, atau mengubah tampilan HTML/CSS/JS di server.py atau halaman web lainnya.
---

# Standar Desain Web Dashboard Ramah Orang Awam (Interaktif, Jelas, Anti-AI-Slop)

Tujuan: siapa pun di pabrik (mandor, admin gudang, pemilik) yang awam teknologi bisa memahami kondisi loading es, membedakan truk aktif vs total harian, memverifikasi kejadian lewat foto/video, dan bertindak dengan tepat dalam **3 detik** tanpa pernah salah paham (*not misguided*).

## 1. Larangan Keras ("AI Slop")
- DILARANG memakai gaya klise AI: tema gelap neon ungu/cyan, kaca buram (*glassmorphism*), animasi berkedip/denyut berlebihan, atau 5–6 kartu angka seragam yang isinya membingungkan.
- DILARANG menampilkan jargon teknis ke pengguna awam: jangan tulis `FPS`, `YOLO Conf`, `ByteTrack ID`, `Inference Latency`, `Stream Buffer`, `Active Anomalies`, `Tripwire`, `ROI`, atau `API Key` mentah.
- DILARANG menampilkan grafik hiasan atau tombol simulasi pengujian di layar operasional produksi.

## 2. Aturan Anti-Salah Paham ("Not Misguided")
Orang awam sering salah menafsirkan dashboard jika konteks waktu, status, dan batasan tidak tertulis gamblang. Wajib terapkan 5 pengaman ini:
1. **Pisahkan Tegas "Truk Sekarang" vs "Rekap Hari Ini":**
   - Jangan campur total satu hari dengan muatan truk yang sedang parkir.
   - Bagian utama (kiri/atas, angka paling besar) = **"Truk yang Sedang Dimuat Sekarang"** (lengkap dengan plat nomor & jam mulai).
   - Strip terpisah berlabel jelas = **"Total Gabungan Semua Truk Hari Ini (mis. 4 Truk · 182 Kantong)"**.
2. **Bedakan Jelas 3 Kondisi Keamanan (Jangan Bikin Panik Palsu):**
   - **Hijau (`AMAN`):** Semua es masuk truk sesuai jalur.
   - **Kuning lembut (`SEDANG DIPANTAU`):** *"1 es sempat jatuh/ditaruh di samping — menunggu apakah diangkat masuk truk."* (Tulis tegas: **Belum dihitung pencurian**).
   - **Merah tegas (`PERINGATAN PENCURIAN`):** *"1 es keluar ke samping dan hilang >10 detik / tertinggal."* Sertakan tombol langsung untuk melihat video bukti.
3. **Sertakan Rincian Ukuran & Jalur Masuk (Bukan Angka Gelondongan):**
   - Tampilkan breakdown jujur: **Total = Es Besar + Es Kecil** (mis. `32 Kantong · 28 Besar + 4 Kecil`).
   - Jika plat nomor belum terbaca kamera, tulis **"Menunggu plat truk terlihat..."**, jangan tampilkan `"-"` kosong yang terlihat seperti error.
4. **Status Kesegaran Data & Kamera Mati:**
   - Jika kamera putus atau pemantauan berhenti (`Standby`), layar tidak boleh tampak seolah-olah masih aktif menghitung (`0` baru). Tampilkan banner kuning/merah yang jelas: **"Pemantauan Berhenti / Kamera Terputus — Angka berhenti pada pukul 10:15"** dan selalu tampilkan waktu update terakhir (*"Diperbarui 2 detik lalu"*).
5. **Tampilkan Kejadian yang Dibatalkan Secara Terpisah (Untuk Kepercayaan):**
   - Kasus *"Es sempat jatuh ke samping lalu dimasukkan lagi ke truk"* ditampilkan sebagai informasi positif bernada tenang (*"Batal Otomatis · Es sudah masuk truk"*), tidak dijumlahkan ke angka "Insiden/Pencurian" merah agar bos/mandor tidak salah kira terjadi pencurian.

## 3. Arah Desain Visual (Bersih, Terang, Kontras Tinggi)
- **Palet Operasional Pabrik (Daylight High-Contrast):** Gunakan latar bersih abu sangat muda/putih hangat (`#F8FAFC` / `#FFFFFF`), teks gelap tegas (`#0F172A`), garis tepi rapi (`#E2E8F0`), dan angka `tabular-nums` besar agar mudah dibaca dari monitor pabrik jarak 1–2 meter tanpa silau.
- **Maksimal 3 Warna Status Bermakna:** Hijau (`#059669` = Aman/Aktif), Kuning/Amber (`#D97706` = Dipantau/Terjeda), Merah (`#DC2626` = Alarm Pencurian/Kamera Putus).
- **Urutan Layar yang Alami:**
  1. **Bar Status Atas:** Status kamera (`Kamera Menyala`), pemilih kamera (`CAM 3` / `CAM 10`), indikator kesegaran data, info user login & tombol **Keluar (Logout)**.
  2. **Zona Utama (2 Kolom Utama):**
     - **Kiri (~60%):** Video CCTV langsung dengan gambar kotak & garis hitung yang bersih, plus tab ganti kamera `CAM 3` / `CAM 10` (atau tampil berdampingan).
     - **Kanan (~40%):** Kartu besar **"Truk Aktif Saat Ini"** (`Total`, `Es Besar`, `Es Kecil`, `Plat Nomor`, `Jam Mulai`) + **Linimasa Foto Terakhir** (3–5 foto potongan kantong es terakhir beserta jam & keterangan singkatnya, mis. *"10:42 · +1 Es Besar (Masuk lewat papan)"*).
  3. **Panel Peringatan & Video Bukti:** Daftar insiden dengan kalimat kronologi lengkap dan tombol **"Putar Video Bukti"**.
  4. **Riwayat Truk & Unduh Laporan:** Tabel truk hari ini + filter tanggal & tombol unduh laporan rapi (CSV/Excel) untuk admin gudang.

## 4. Fitur Interaktif yang Membantu (Tanpa Memperumit)
- **Linimasa Foto Hitungan Langsung:** Klik setiap baris hitungan terbaru untuk memperbesar foto kantong es yang barusan terhitung (membuat operator langsung percaya hasil hitungan AI).
- **Modal Video Bukti Dalam Halaman:** Klik **"Putar Video Bukti"** langsung membuka pemutar video *pop-up* rapi di halaman yang sama (tidak melempar user ke tab baru berisi link API mentah), lengkap dengan tombol Play/Pause & Unduh.
- **Detail Truk Interaktif (*Slide-over / Modal*):** Klik salah satu baris di tabel Riwayat Truk untuk melihat rincian per menit, jalur masuk (papan / samping kembali / lempar langsung), dan semua bukti video di trip tersebut.
- **Filter Interaktif Sederhana:** Pilihan chip sekali klik (`Hari Ini`, `Kemarin`, `Pilih Tanggal`, `Semua`, `Hanya Alarm`, `Hanya Batal Otomatis`).
- **Ikon Bantuan (`?`) Bahasa Manusia:** Di sebelah istilah seperti *"Batal Otomatis"* atau *"Kamera Terputus"*, sediakan ikon `?` yang saat diklik/disentuh memunculkan penjelasan 1 kalimat sederhana.
- **Kontrol Aman Sesuai Peran:**
  - Operator biasa: mode pantau bersih, pilih kamera, filter tanggal, putar video bukti.
  - Admin: tambahan kontrol **Mulai / Hentikan Pemantauan** (dengan dialog konfirmasi agar tidak kepencet), ganti sumber kamera, dan **Ekspor Laporan**.

## 5. Bahasa Sehari-hari & Pesan Error yang Ramah
- `Stream Connected / Disconnected` → **Kamera Menyala** / **Kamera Terputus — Periksa kabel atau listrik CCTV**
- `Truck OCR` → **Plat Nomor Truk**
- `Total Package (Large / Small)` → **Total Es Masuk Truk** (`Es Besar` & `Es Kecil`)
- `Suspected Theft / Anomaly` → **Peringatan Pencurian** vs **Sempat ke Samping (Sudah Masuk Truk)**
- Pesan error HTTP (`401/403/500/timeout`) → Tampilkan pesan ramah seperti *"Sesi login habis, silakan masuk kembali"* atau *"Koneksi ke komputer server terputus, sedang menyambung ulang..."*, bukan JSON/stack trace.

## 6. Keamanan Frontend Web Dashboard
- **Wajib Anti-XSS:** Semua data dinamis (plat truk, detail alarm, nama file, event) WAJIB dirender lewat `textContent` / DOM API (`createElement`), dilarang keras menyusun HTML lewat template string ke `innerHTML`.
- **Login, Session & Anti-Direct-URL:** Halaman dashboard, feed video CCTV, daftar trip, dan video bukti wajib terlindungi sesi login (`HttpOnly` cookie), menonaktifkan aksi via URL `GET`, serta membersihkan tampilan saat Logout / *idle timeout*.
- **Masking Kredensial:** Jangan pernah mengirim password/URL RTSP lengkap atau token ke JavaScript browser maupun menampilkannya di UI.
