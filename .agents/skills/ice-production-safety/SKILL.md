---
name: ice-production-safety
description: Checklist keamanan, rahasia, dan keandalan 24/7 untuk sistem monitoring es (API key, .env, CORS, git hygiene, soak test, mati listrik/CCTV putus). Gunakan sebelum deploy ke pabrik atau saat mengubah server/security/config.
---

# Keamanan & keandalan produksi

## Rahasia
- `API_SECRET_KEY` = password admin buatan sendiri: `python -c "import secrets;print(secrets.token_urlsafe(32))"` lalu taruh di `.env`. Dashboard meminta key saat menekan tombol admin.
- Supabase key/URL/password DB dari dashboard Supabase (Project Settings -> API / Database). Telegram token dari @BotFather.
- `.env` tidak boleh ter-commit. Jika rahasia pernah masuk git, ROTASI, jangan hanya hapus.

## Server
- `REQUIRE_API_KEY=true`, `API_HOST=127.0.0.1` kecuali butuh LAN (lalu pakai reverse proxy + HTTPS), `CORS_ORIGINS` spesifik.
- Setiap endpoint yang mengubah state wajib `Depends(verify_api_key)`.

## Keandalan 24/7
- Uji soak minimal 72 jam: pantau memori, FPS, disk, jumlah thread, reconnect RTSP.
- Uji skenario: CCTV dicabut, mati listrik, disk hampir penuh, internet putus (antrean Telegram & sync cloud harus pulih).
- Jalankan sebagai service (NSSM/Task Scheduler) dengan restart otomatis.
- Mode shadow dulu (catat tanpa alarm) sebelum alarm penuh.
- Hash SHA-256 bukti sebaiknya juga dikirim ke cloud agar tidak bisa dimanipulasi lokal.

## Sebelum deploy
`python -m pytest tests -q` hijau; `git status` bersih dari rahasia/video besar; semua parameter cabang di `.env`/`branch_profile.json`.
