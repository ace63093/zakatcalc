"""SQLite database connection management for pricing data."""
import os
import sqlite3
from flask import current_app, g


def get_db_path() -> str:
    """Get the path to the SQLite database file."""
    data_dir = current_app.config.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'pricing.sqlite')


def get_db() -> sqlite3.Connection:
    """Get a database connection, creating one if needed for this request."""
    if 'db' not in g:
        g.db = sqlite3.connect(get_db_path())
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close the database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database with schema."""
    db = get_db()
    db.executescript(get_schema())
    db.commit()


def get_schema() -> str:
    """Return the database schema SQL."""
    return '''
-- FX rates table (all rates stored as USD base: 1 USD = X currency)
-- snapshot_type: 'weekly' (Monday), 'monthly' (1st of month), or 'daily' (legacy)
CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate_to_usd REAL NOT NULL,
    source TEXT,
    snapshot_type TEXT DEFAULT 'daily',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, currency)
);
CREATE INDEX IF NOT EXISTS idx_fx_rates_date ON fx_rates(date);
CREATE INDEX IF NOT EXISTS idx_fx_rates_currency ON fx_rates(currency);
CREATE INDEX IF NOT EXISTS idx_fx_rates_snapshot ON fx_rates(date, snapshot_type);

-- Metal prices table (USD per gram)
-- snapshot_type: 'weekly' (Monday), 'monthly' (1st of month), or 'daily' (legacy)
CREATE TABLE IF NOT EXISTS metal_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    metal TEXT NOT NULL,
    price_per_gram_usd REAL NOT NULL,
    source TEXT,
    snapshot_type TEXT DEFAULT 'daily',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, metal)
);
CREATE INDEX IF NOT EXISTS idx_metal_prices_date ON metal_prices(date);
CREATE INDEX IF NOT EXISTS idx_metal_prices_metal ON metal_prices(metal);
CREATE INDEX IF NOT EXISTS idx_metal_prices_snapshot ON metal_prices(date, snapshot_type);

-- Crypto prices table (USD per coin)
-- snapshot_type: 'weekly' (Monday), 'monthly' (1st of month), or 'daily' (legacy)
CREATE TABLE IF NOT EXISTS crypto_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    price_usd REAL NOT NULL,
    rank INTEGER,
    source TEXT,
    snapshot_type TEXT DEFAULT 'daily',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_date ON crypto_prices(date);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_symbol ON crypto_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_rank ON crypto_prices(rank);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_snapshot ON crypto_prices(date, snapshot_type);

-- Crypto assets master table (top 100 ordering, separate from daily prices)
CREATE TABLE IF NOT EXISTS crypto_assets (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_crypto_assets_rank ON crypto_assets(rank);

-- Sync log for tracking sync operations
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_date TEXT NOT NULL,
    data_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    records_count INTEGER,
    error_message TEXT,
    snapshot_type TEXT DEFAULT 'daily',
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sync_log_date ON sync_log(sync_date, data_type);

-- Daemon state table for tracking background sync service status
CREATE TABLE IF NOT EXISTS daemon_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_sync_at TEXT,
    last_sync_result TEXT,
    last_error TEXT,
    next_sync_at TEXT,
    snapshots_synced INTEGER DEFAULT 0,
    daemon_version TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Metadata table for tracking import/update status
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- IP geolocation: parsed Apple CSV CIDR ranges
--   ip_start/ip_end: zero-padded hex for sortable range queries
--   ip_version: 4 or 6
CREATE TABLE IF NOT EXISTS ip_geolocation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_start TEXT NOT NULL,
    ip_end TEXT NOT NULL,
    cidr TEXT NOT NULL,
    country_code TEXT NOT NULL,
    region_code TEXT,
    city TEXT,
    ip_version INTEGER NOT NULL DEFAULT 4,
    UNIQUE(cidr)
);
CREATE INDEX IF NOT EXISTS idx_ip_geo_v4_range ON ip_geolocation(ip_version, ip_start, ip_end);

-- Visitors: unique visitor log, keyed by IP string.
-- Note: column name ip_hash is legacy and now stores plain IP values.
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_hash TEXT NOT NULL,
    country_code TEXT,
    region_code TEXT,
    city TEXT,
    user_agent TEXT,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    visit_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE(ip_hash)
);
CREATE INDEX IF NOT EXISTS idx_visitors_country ON visitors(country_code);
CREATE INDEX IF NOT EXISTS idx_visitors_last_seen ON visitors(last_seen);

-- Visitor domains: per-domain visit tracking per visitor IP key.
CREATE TABLE IF NOT EXISTS visitor_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_hash TEXT NOT NULL,
    host TEXT NOT NULL,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    visit_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE(ip_hash, host)
);
CREATE INDEX IF NOT EXISTS idx_visitor_domains_host ON visitor_domains(host);
CREATE INDEX IF NOT EXISTS idx_visitor_domains_last_seen ON visitor_domains(last_seen);
'''


def init_app(app):
    """Register database functions with Flask app and ensure database exists."""
    app.teardown_appcontext(close_db)

    # Ensure database schema is initialized on app startup
    with app.app_context():
        # Always run schema (CREATE IF NOT EXISTS handles idempotency)
        # This ensures tables exist even if file was just created
        db = get_db()
        db.executescript(get_schema())
        db.commit()
