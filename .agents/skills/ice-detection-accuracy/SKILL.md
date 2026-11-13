---
name: ice-detection-accuracy
description: Alur mengukur dan meningkatkan akurasi deteksi/penghitungan es dan alarm pencurian (ground truth, precision/recall, false alarm per jam, split data). Gunakan saat user memberi video baru, menanyakan akurasi, atau mengubah model/threshold/logika alarm.
---

# Mengukur akurasi sistem deteksi es

## Prinsip
1. Ground truth = catatan manual manusia, dibuat TANPA melihat output sistem. `scratch/gt_audit/events.txt` BUKAN ground truth (itu output sistem).
2. Video uji tidak boleh dipakai untuk training. Split per video, bukan per frame.
3. Laporkan angka, bukan opini.

## Alur
1. Terima video baru; catat nama, durasi, kondisi (siang/malam, truk, kamera). Jangan dipakai training dulu.
2. Minta user menandai kejadian (atau tandai bersama): file `ground_truth/<video>.csv` dengan kolom `time_sec,event,size,note`. event: `package_in`, `side_exit_theft`, `side_exit_recovered`, `truck_arrive`, `truck_leave`.
   Untuk video false-positive: cukup tandai hanya kejadian yang PASTI nyata; sistem yang mengeluarkan alarm di luar daftar = false positive.
3. Jalankan sistem pada video (headless), simpan event (waktu, jenis) ke `eval/<video>_pred.csv`.
4. Cocokkan dengan toleransi +-2 detik: TP, FP, FN.
5. Hitung: precision, recall, F1, FP per jam, selisih total hitungan (sistem vs manusia) per trip.
6. Analisis tiap FP/FN: simpan frame sekitar kejadian, kategorikan penyebab (oklusi, ID switch, bayangan, orang, tumpukan, ROI).
7. Perbaiki: pilih yang paling murah dulu (aturan/ROI/temporal filter) sebelum retrain. Kalau retrain: masukkan frame FP sebagai hard negative ke dataset TRAIN, bukan video uji.
8. Ulangi evaluasi di SEMUA video uji; pastikan tidak ada regresi.

## Target awal (sesuaikan dengan user)
- Hitungan es: error <= 2% per trip.
- Alarm pencurian: recall >= 90%, false alarm < 1 per shift.
- Mode shadow 1-2 minggu di pabrik sebelum alarm Telegram penuh.
