-- GuardHome database schema

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS children (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    age        INTEGER,
    avatar     TEXT,
    preset     TEXT NOT NULL DEFAULT 'middle_school',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    birthday   TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mac         TEXT UNIQUE NOT NULL,
    hostname    TEXT,
    ip          TEXT,
    label       TEXT,
    device_type TEXT,
    child_id    INTEGER REFERENCES children(id) ON DELETE SET NULL,
    last_seen   TEXT
);

-- Per-child category toggles (overrides inherit from preset)
CREATE TABLE IF NOT EXISTS category_rules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id   INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    blocked    INTEGER NOT NULL DEFAULT 1,
    UNIQUE(child_id, category)
);

-- Time schedules (e.g. bedtime, school mode)
CREATE TABLE IF NOT EXISTS schedules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id   INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    days       TEXT NOT NULL,  -- JSON array: ["Mon","Tue","Wed","Thu","Fri"]
    start_time TEXT NOT NULL,  -- "HH:MM" 24h
    end_time   TEXT NOT NULL,
    action     TEXT NOT NULL DEFAULT 'block_all',  -- block_all | category_block
    enabled    INTEGER NOT NULL DEFAULT 1
);

-- Per-child always-on educational exceptions
CREATE TABLE IF NOT EXISTS allow_exceptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id   INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    domain     TEXT NOT NULL,
    label      TEXT,
    UNIQUE(child_id, domain)
);

-- DNS query log (synced from AdGuard)
CREATE TABLE IF NOT EXISTS dns_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    client_ip  TEXT,
    domain     TEXT NOT NULL,
    answer     TEXT,
    blocked    INTEGER NOT NULL DEFAULT 0,
    rule       TEXT,
    child_id   INTEGER REFERENCES children(id) ON DELETE SET NULL
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL DEFAULT (datetime('now')),
    child_id   INTEGER REFERENCES children(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL,
    title      TEXT NOT NULL,
    detail     TEXT,
    read       INTEGER NOT NULL DEFAULT 0
);

-- Classifier cache
CREATE TABLE IF NOT EXISTS domain_classifications (
    domain     TEXT PRIMARY KEY,
    category   TEXT,
    confidence REAL,
    source     TEXT,  -- blocklist | url_api | ai
    cached_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL DEFAULT (datetime('now')),
    user       TEXT NOT NULL DEFAULT 'parent',
    action     TEXT NOT NULL,
    detail     TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_dns_log_ts       ON dns_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_dns_log_client   ON dns_log(client_ip);
CREATE INDEX IF NOT EXISTS idx_dns_log_child    ON dns_log(child_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unread    ON alerts(child_id, read);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dns_log    ON dns_log(child_id, domain, ts);
