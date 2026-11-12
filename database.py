import sqlite3
import os
import logging
from datetime import datetime, date
from config import DB_PATH, DEFAULT_CITY

logger = logging.getLogger(__name__)


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Aktifkan WAL (Write-Ahead Logging) agar tahan mati lampu mendadak (anti-corruption)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            city            TEXT DEFAULT 'Makassar',
            truck_id        TEXT,
            truck_raw_ocr   TEXT,
            trip_date       TEXT,
            trip_number     INTEGER DEFAULT 1,
            start_time      TEXT,
            end_time        TEXT,
            duration_sec    INTEGER,
            count_large     INTEGER DEFAULT 0,
            count_small     INTEGER DEFAULT 0,
            count_total     INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'ongoing',
            notes           TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS package_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER,
            timestamp       TEXT,
            frame_idx       INTEGER DEFAULT 0,
            size            TEXT,
            area_px         INTEGER,
            trajectory_type TEXT DEFAULT 'chute',
            direction       TEXT DEFAULT 'in',
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER,
            timestamp       TEXT,
            frame_idx       INTEGER,
            anomaly_type    TEXT,
            status          TEXT DEFAULT 'PENDING',
            video_clip_path TEXT DEFAULT '',
            telegram_sent   INTEGER DEFAULT 0,
            details         TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # Migrasi kolom jika tabel lama sudah ada
    cur.execute("PRAGMA table_info(sessions)")
    existing_cols = [r['name'] for r in cur.fetchall()]
    new_cols = {
        'branch_code': "TEXT DEFAULT 'MKS-01'",
        'city': "TEXT DEFAULT 'Makassar'",
        'trip_date': "TEXT",
        'trip_number': "INTEGER DEFAULT 1"
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE sessions ADD COLUMN {col} {col_type}")
                logger.info(f"[DB] Ditambahkan kolom {col} pada tabel sessions")
            except Exception as e:
                logger.warning(f"[DB] Gagal menambah kolom {col}: {e}")

    # Migrasi anomalies untuk multi-branch
    cur.execute("PRAGMA table_info(anomalies)")
    anom_cols = [r['name'] for r in cur.fetchall()]
    anom_new = {
        'branch_code': "TEXT DEFAULT 'MKS-01'",
        'city': "TEXT DEFAULT 'Makassar'"
    }
    for col, col_type in anom_new.items():
        if col not in anom_cols:
            try:
                cur.execute(f"ALTER TABLE anomalies ADD COLUMN {col} {col_type}")
            except Exception:
                pass

    # Migrasi package_events
    cur.execute("PRAGMA table_info(package_events)")
    pkg_cols = [r['name'] for r in cur.fetchall()]
    pkg_new = {
        'frame_idx': 'INTEGER DEFAULT 0',
        'trajectory_type': "TEXT DEFAULT 'chute'",
        'direction': "TEXT DEFAULT 'in'"
    }
    for col, col_type in pkg_new.items():
        if col not in pkg_cols:
            try:
                cur.execute(f"ALTER TABLE package_events ADD COLUMN {col} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()
    logger.info(f"Database siap: {DB_PATH}")


def create_session(truck_id: str, truck_raw_ocr: str, city: str = DEFAULT_CITY) -> int:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    now_dt = datetime.now()
    now_iso = now_dt.isoformat(timespec='seconds')
    today_str = now_dt.strftime('%Y-%m-%d')

    # Hitung trip ke berapa untuk truk ini di hari yang sama
    cur.execute("""
        SELECT COUNT(*) as trip_count
        FROM sessions
        WHERE (truck_id = ? OR truck_raw_ocr = ?)
          AND (trip_date = ? OR start_time LIKE ?)
    """, (truck_id, truck_raw_ocr, today_str, f"{today_str}%"))
    row = cur.fetchone()
    trip_number = (row['trip_count'] if row else 0) + 1

    cur.execute("""
        INSERT INTO sessions (
            city, truck_id, truck_raw_ocr, trip_date, trip_number, start_time, status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'ongoing')
    """, (city, truck_id, truck_raw_ocr, today_str, trip_number, now_iso))

    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.info(
        f"[DB] Sesi baru dibuat: ID={session_id}, Kota='{city}', Truk='{truck_id}', "
        f"Trip ke-{trip_number}, Mulai={now_iso}"
    )
    return session_id


def update_truck_id(session_id: int, truck_id: str, truck_raw_ocr: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE sessions SET truck_id=?, truck_raw_ocr=? WHERE id=?
    """, (truck_id, truck_raw_ocr, session_id))
    conn.commit()
    conn.close()


def log_package(session_id: int, size: str, area_px: int, frame_idx: int = 0,
                trajectory: str = "chute", direction: str = "in"):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec='seconds')

    cur.execute("""
        INSERT INTO package_events (
            session_id, timestamp, frame_idx, size, area_px, trajectory_type, direction
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, now, frame_idx, size, area_px, trajectory, direction))

    increment = 1 if direction == "in" else -1

    if size == 'large':
        cur.execute("""
            UPDATE sessions
            SET count_large = MAX(0, count_large + ?),
                count_total = MAX(0, count_total + ?)
            WHERE id = ?
        """, (increment, increment, session_id))
    else:
        cur.execute("""
            UPDATE sessions
            SET count_small = MAX(0, count_small + ?),
                count_total = MAX(0, count_total + ?)
            WHERE id = ?
        """, (increment, increment, session_id))

    conn.commit()
    conn.close()


def log_anomaly(session_id: int, frame_idx: int, anomaly_type: str,
                status: str = 'PENDING', video_clip_path: str = '', details: str = '') -> int:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec='seconds')
    cur.execute("""
        INSERT INTO anomalies (
            session_id, timestamp, frame_idx, anomaly_type, status, video_clip_path, details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, now, frame_idx, anomaly_type, status, video_clip_path, details))
    anomaly_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.warning(
        f"[ANOMALY] Terdaftar: ID={anomaly_id}, Trip={session_id}, Tipe={anomaly_type}, "
        f"Status={status}, Frame={frame_idx}"
    )
    return anomaly_id


def update_anomaly(anomaly_id: int, status: str = None, video_clip_path: str = None,
                   telegram_sent: bool = None, details: str = None):
    conn = get_connection()
    cur = conn.cursor()
    updates = []
    params = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if video_clip_path is not None:
        updates.append("video_clip_path = ?")
        params.append(video_clip_path)
    if telegram_sent is not None:
        updates.append("telegram_sent = ?")
        params.append(1 if telegram_sent else 0)
    if details is not None:
        updates.append("details = ?")
        params.append(details)

    if updates:
        params.append(anomaly_id)
        cur.execute(f"UPDATE anomalies SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()


def close_session(session_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    now_dt = datetime.now()
    now_iso = now_dt.isoformat(timespec='seconds')

    cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {}

    try:
        start_dt = datetime.fromisoformat(row['start_time'])
        duration = int((now_dt - start_dt).total_seconds())
    except Exception:
        duration = 0

    cur.execute("""
        UPDATE sessions
        SET end_time=?, duration_sec=?, status='completed'
        WHERE id=?
    """, (now_iso, duration, session_id))
    conn.commit()

    cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    final = dict(cur.fetchone())
    conn.close()

    logger.info(
        f"[DB] Sesi selesai: ID={session_id} | Truk={final['truck_id']} | "
        f"Trip #{final['trip_number']} | Besar={final['count_large']} | "
        f"Kecil={final['count_small']} | Total={final['count_total']} | Durasi={duration}s"
    )
    return final


def get_all_sessions(city: str = None, target_date: str = None, truck_id: str = None) -> list:
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM sessions WHERE 1=1"
    params = []
    if city:
        query += " AND city = ?"
        params.append(city)
    if target_date:
        query += " AND (trip_date = ? OR start_time LIKE ?)"
        params.extend([target_date, f"{target_date}%"])
    if truck_id:
        query += " AND (truck_id = ? OR truck_raw_ocr = ?)"
        params.extend([truck_id, truck_id])

    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_session_detail(session_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {}
    res = dict(row)

    cur.execute("SELECT * FROM package_events WHERE session_id=? ORDER BY id ASC", (session_id,))
    res['events'] = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM anomalies WHERE session_id=? ORDER BY id DESC", (session_id,))
    res['anomalies'] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return res


def get_daily_summary(city: str = DEFAULT_CITY, target_date: str = None) -> dict:
    if target_date is None:
        target_date = date.today().strftime('%Y-%m-%d')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            COUNT(DISTINCT truck_id) as total_trucks,
            COUNT(id) as total_trips,
            COALESCE(SUM(count_large), 0) as total_large,
            COALESCE(SUM(count_small), 0) as total_small,
            COALESCE(SUM(count_total), 0) as grand_total
        FROM sessions
        WHERE (city = ? OR city IS NULL)
          AND (trip_date = ? OR start_time LIKE ?)
    """, (city, target_date, f"{target_date}%"))

    summary = dict(cur.fetchone())
    summary['city'] = city
    summary['date'] = target_date

    # Ambil list trip hari ini
    cur.execute("""
        SELECT id, city, truck_id, truck_raw_ocr, trip_number,
               start_time, end_time, duration_sec, count_large,
               count_small, count_total, status
        FROM sessions
        WHERE (city = ? OR city IS NULL)
          AND (trip_date = ? OR start_time LIKE ?)
        ORDER BY id DESC
    """, (city, target_date, f"{target_date}%"))
    summary['trips'] = [dict(r) for r in cur.fetchall()]

    # Ambil anomali hari ini
    cur.execute("""
        SELECT a.*, s.truck_id, s.trip_number
        FROM anomalies a
        JOIN sessions s ON a.session_id = s.id
        WHERE (s.city = ? OR s.city IS NULL)
          AND (s.trip_date = ? OR s.start_time LIKE ?)
        ORDER BY a.id DESC
    """, (city, target_date, f"{target_date}%"))
    summary['anomalies'] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return summary


def get_anomalies(session_id: int = None, limit: int = 50) -> list:
    conn = get_connection()
    cur = conn.cursor()
    if session_id:
        cur.execute("""
            SELECT a.*, s.truck_id, s.trip_number, s.city
            FROM anomalies a
            JOIN sessions s ON a.session_id = s.id
            WHERE a.session_id = ?
            ORDER BY a.id DESC LIMIT ?
        """, (session_id, limit))
    else:
        cur.execute("""
            SELECT a.*, s.truck_id, s.trip_number, s.city
            FROM anomalies a
            JOIN sessions s ON a.session_id = s.id
            ORDER BY a.id DESC LIMIT ?
        """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
