import sqlite3
import os
import sys
import csv
from datetime import datetime, date
from config import DB_PATH


def print_table(rows: list, headers: list):
    if not rows:
        print("(Tidak ada data)\n")
        return
    widths = [max(len(str(h)), max(len(str(r[i])) for r in rows))
              for i, h in enumerate(headers)]
    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    hrow = "| " + " | ".join(str(h).center(w) for h, w in zip(headers, widths)) + " |"
    print(sep)
    print(hrow)
    print(sep)
    for row in rows:
        line = "| " + " | ".join(str(v).ljust(w) for v, w in zip(row, widths)) + " |"
        print(line)
    print(sep)
    print()


def report_all():
    if not os.path.exists(DB_PATH):
        print("Database belum ada. Jalankan main.py dulu.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, truck_id, start_time, end_time,
               duration_sec, count_large, count_small, count_total, status
        FROM sessions
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("Belum ada sesi yang tersimpan.")
        return

    print(f"\n{'='*70}")
    print("       LAPORAN SESI LOADING KEMASAN ES KRISTAL")
    print(f"       Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    table_rows = []
    total_large = total_small = total_all = 0

    for r in rows:
        dur = r['duration_sec'] or 0
        dur_str = f"{dur//60}m {dur%60}s"
        start = r['start_time'][:16] if r['start_time'] else '-'
        table_rows.append([
            r['id'],
            r['truck_id'] or '-',
            start,
            dur_str,
            r['count_large'],
            r['count_small'],
            r['count_total'],
            r['status'],
        ])
        total_large += r['count_large'] or 0
        total_small += r['count_small'] or 0
        total_all += r['count_total'] or 0

    print_table(table_rows, [
        "ID", "Truk", "Mulai", "Durasi",
        "Besar", "Kecil", "Total", "Status"
    ])

    print(f"  GRAND TOTAL → Besar: {total_large} | Kecil: {total_small} | SEMUA: {total_all}\n")


def report_today():
    if not os.path.exists(DB_PATH):
        print("Database belum ada.")
        return

    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, truck_id, start_time, end_time,
               duration_sec, count_large, count_small, count_total, status
        FROM sessions
        WHERE DATE(start_time) = ?
        ORDER BY id
    """, (today,))
    rows = cur.fetchall()
    conn.close()

    print(f"\n{'='*60}")
    print(f"  LAPORAN HARI INI ({today})")
    print(f"{'='*60}\n")

    if not rows:
        print("  Belum ada loading hari ini.\n")
        return

    table_rows = []
    total_large = total_small = total_all = 0

    for r in rows:
        dur = r['duration_sec'] or 0
        dur_str = f"{dur//60}m {dur%60}s"
        start = r['start_time'][11:16] if r['start_time'] else '-'
        end = r['end_time'][11:16] if r['end_time'] else '-'
        table_rows.append([
            r['id'],
            r['truck_id'] or '-',
            start, end,
            dur_str,
            r['count_large'],
            r['count_small'],
            r['count_total'],
        ])
        total_large += r['count_large'] or 0
        total_small += r['count_small'] or 0
        total_all += r['count_total'] or 0

    print_table(table_rows, [
        "ID", "Truk", "Mulai", "Selesai", "Durasi",
        "Besar", "Kecil", "Total"
    ])

    print(f"  Total Hari Ini → Besar: {total_large} | Kecil: {total_small} | SEMUA: {total_all}\n")


def export_csv(filename: str = "laporan_loading.csv"):
    if not os.path.exists(DB_PATH):
        print("Database belum ada.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, truck_id, truck_raw_ocr, start_time, end_time,
               duration_sec, count_large, count_small, count_total, status
        FROM sessions
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("Belum ada data untuk diekspor.")
        return

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID Sesi", "Nomor Truk", "OCR Raw", "Waktu Mulai",
            "Waktu Selesai", "Durasi (Detik)", "Kemasan Besar",
            "Kemasan Kecil", "Total Kemasan", "Status Sesi"
        ])
        for r in rows:
            writer.writerow([
                r['id'], r['truck_id'], r['truck_raw_ocr'],
                r['start_time'], r['end_time'], r['duration_sec'],
                r['count_large'], r['count_small'], r['count_total'],
                r['status']
            ])

    print(f"\nLaporan berhasil diekspor ke: {filename}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower()
        if arg in ("2", "today", "--today"):
            report_today()
        elif arg in ("3", "csv", "--csv", "export"):
            export_csv()
        else:
            report_all()
    else:
        print("\n[1] Semua sesi")
        print("[2] Hari ini saja")
        print("[3] Ekspor ke file CSV (Excel)")
        try:
            pilihan = input("Pilih (1/2/3, default=1): ").strip() or "1"
        except EOFError:
            pilihan = "1"

        if pilihan == "2":
            report_today()
        elif pilihan == "3":
            export_csv()
        else:
            report_all()
