---
name: ice-false-positive-debug
description: Prosedur menyelidiki false positive/negative pada alarm pencurian dan hitungan es (state machine side-exit, tracker ByteTrack, ROI/zona). Gunakan saat user melaporkan alarm palsu atau hitungan salah pada sebuah video/frame.
---

# Debug false positive

## Konteks logika (engine.py)
- Objek di zona samping (x < CHUTE_MIN_X atau x > CHUTE_MAX_X, y > TRUCK_ENTRANCE_Y) -> status PENDING (anomali dicatat).
- Kembali ke zona truk (TRUCK_MIN_X..TRUCK_MAX_X, y <= TRUCK_ENTRANCE_Y) dalam SIDE_RECOVERY_WINDOW_FRAMES -> dibatalkan (anomali dihapus).
- Window habis -> CONFIRMED_THEFT, rekam bukti, Telegram. Tracking hilang sesaat TIDAK langsung dianggap pencurian.

## Langkah
1. Minta waktu/frame kejadian dari user. Ekstrak klip +-10 detik.
2. Telusuri per frame: posisi centroid, ID tracker, confidence, zona yang dimasuki, kapan PENDING terbuat. Gunakan skrip di `scratch/trace_*.py` sebagai contoh, tapi simpan skrip baru di `scratch/`.
3. Klasifikasi penyebab:
   - ID switch / tracker kehilangan objek -> longgarkan matching, naikkan TRACKER_MAX_MISSING, atau gabung berdasarkan jarak & waktu.
   - Orang/objek non-es terdeteksi -> hard negative untuk training, atau filter ukuran (MIN/MAX_PACKAGE_AREA).
   - Es memantul lalu masuk lagi -> perpanjang jendela pemulihan.
   - Kamera bergeser -> kalibrasi ulang ROI (`calibrate.py`).
   - Bayangan/pencahayaan -> augmentasi data, jangan hanya ubah threshold.
4. Buat TEST yang mereproduksi kasus (di `tests/test_state_machine.py`) sebelum memperbaiki.
5. Perbaiki dengan perubahan sekecil mungkin; parameter ke `config.py`.
6. Jalankan seluruh tes + evaluasi ulang semua video (lihat `ice-detection-accuracy`). Laporkan sebelum/sesudah dalam angka.
