-- ==============================================================
-- SCHEMA POSTGRESQL / SUPABASE UNTUK MONITORING ES KRISTAL
-- Multi-Branch Nationwide (Mendukung Seluruh Cabang di Indonesia)
-- ==============================================================

-- 1. Tabel Sesi Loading Truk
CREATE TABLE IF NOT EXISTS sessions (
    id              BIGINT PRIMARY KEY,
    branch_code     TEXT DEFAULT 'MKS-01',
    city            TEXT DEFAULT 'Makassar',
    truck_id        TEXT,
    truck_raw_ocr   TEXT,
    trip_date       DATE DEFAULT CURRENT_DATE,
    trip_number     INT DEFAULT 1,
    start_time      TEXT,
    end_time        TEXT,
    duration_sec    INT DEFAULT 0,
    count_large     INT DEFAULT 0,
    count_small     INT DEFAULT 0,
    count_total     INT DEFAULT 0,
    status          TEXT DEFAULT 'ongoing',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabel Anomali & Pencurian Es
CREATE TABLE IF NOT EXISTS anomalies (
    id              BIGINT PRIMARY KEY,
    branch_code     TEXT DEFAULT 'MKS-01',
    city            TEXT DEFAULT 'Makassar',
    session_id      BIGINT REFERENCES sessions(id) ON DELETE SET NULL,
    timestamp       TEXT,
    frame_idx       INT DEFAULT 0,
    anomaly_type    TEXT,
    status          TEXT,
    video_clip_path TEXT,
    telegram_sent   INT DEFAULT 0,
    details         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Index untuk pencarian cepat multi-cabang (Per Kota & Tanggal)
CREATE INDEX IF NOT EXISTS idx_sessions_city_date ON sessions (city, trip_date);
CREATE INDEX IF NOT EXISTS idx_sessions_branch ON sessions (branch_code);
CREATE INDEX IF NOT EXISTS idx_anomalies_city ON anomalies (city);

-- 4. Row Level Security (RLS) - Akses aman multi-cabang
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public Read Sessions" ON sessions FOR SELECT USING (true);
CREATE POLICY "Public Read Anomalies" ON anomalies FOR SELECT USING (true);
CREATE POLICY "Service Insert Sessions" ON sessions FOR ALL USING (true);
CREATE POLICY "Service Insert Anomalies" ON anomalies FOR ALL USING (true);
