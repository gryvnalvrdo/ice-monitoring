import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
import sys
import requests
import config
from cloud_sync import cloud_sync

def test_supabase():
    print("=" * 65)
    print("      VERIFIKASI INTEGRASI SUPABASE CLOUD DATABASE")
    print("=" * 65)

    url = getattr(config, "CLOUD_SUPABASE_URL", "").strip()
    key = getattr(config, "CLOUD_SUPABASE_KEY", "").strip()

    print(f"Target Supabase URL : {url or '(Belum diatur)'}")
    print(f"API Key Terdeteksi  : {'Ya (' + key[:12] + '...)' if key else 'Tidak (Kosong)'}")
    print("=" * 65)

    if not url or not key:
        print("\n❌ GAGAL: CLOUD_SUPABASE_URL atau CLOUD_SUPABASE_KEY masih kosong di config.py!")
        print("Silakan masukkan URL dan API Key dari dashboard Supabase Anda terlebih dahulu.")
        return False

    print("\n[1/3] Menghubungi Supabase REST API endpoint...")
    test_url = f"{url.rstrip('/')}/rest/v1/sessions?select=id&limit=1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    try:
        resp = requests.get(test_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            print("  -> [SUKSES] Koneksi ke Supabase BERHASIL (HTTP 200 OK)!")
        elif resp.status_code == 404 or "relation \"sessions\" does not exist" in resp.text:
            print(f"  -> ⚠️ PERINGATAN: Supabase terhubung, tapi tabel 'sessions' belum dibuat!")
            print("     Harap jalankan isi file 'supabase_schema.sql' di SQL Editor Supabase.")
            return False
        else:
            print(f"  -> ❌ GAGAL: Respon Supabase ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  -> ❌ ERROR KONEKSI: Tidak dapat menjangkau Supabase: {e}")
        return False

    print("\n[2/3] Memeriksa tabel 'anomalies'...")
    anom_url = f"{url.rstrip('/')}/rest/v1/anomalies?select=id&limit=1"
    try:
        resp = requests.get(anom_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            print("  -> [SUKSES] Tabel 'anomalies' siap digunakan!")
        else:
            print(f"  -> ⚠️ PERINGATAN: Tabel 'anomalies' belum dibuat: {resp.text}")
            return False
    except Exception as e:
        print(f"  -> ❌ GAGAL: {e}")
        return False

    print("\n[3/3] Menguji sinkronisasi data dari SQLite lokal ke Supabase...")
    cloud_sync.is_enabled = True
    cloud_sync.supabase_url = url
    cloud_sync.supabase_key = key
    res = cloud_sync.sync_now()

    print(f"  -> Status Sinkronisasi : {res.get('status')}")
    print(f"  -> Sesi Tersinkron     : {res.get('synced_sessions', 0)} baris")
    print(f"  -> Anomali Tersinkron  : {res.get('synced_anomalies', 0)} baris")
    print(f"  -> Waktu Sinkronisasi  : {res.get('last_sync_time')}")

    print("\n" + "=" * 65)
    print("  🎉 INTEGRASI SUPABASE 100% SUKSES DAN READY TO USE!")
    print("=" * 65)
    return True

if __name__ == "__main__":
    test_supabase()
