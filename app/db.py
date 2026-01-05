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
CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate_to_usd REAL NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, currency)
);
CREATE INDEX IF NOT EXISTS idx_fx_rates_date ON fx_rates(date);
CREATE INDEX IF NOT EXISTS idx_fx_rates_currency ON fx_rates(currency);

-- Metal prices table (USD per gram)
CREATE TABLE IF NOT EXISTS metal_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    metal TEXT NOT NULL,
    price_per_gram_usd REAL NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, metal)
);
CREATE INDEX IF NOT EXISTS idx_metal_prices_date ON metal_prices(date);
CREATE INDEX IF NOT EXISTS idx_metal_prices_metal ON metal_prices(metal);

-- Crypto prices table (USD per coin)
CREATE TABLE IF NOT EXISTS crypto_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    price_usd REAL NOT NULL,
    rank INTEGER,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_date ON crypto_prices(date);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_symbol ON crypto_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_crypto_prices_rank ON crypto_prices(rank);

-- Metadata table for tracking import/update status
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
'''


def init_app(app):
    """Register database functions with Flask app."""
    app.teardown_appcontext(close_db)
