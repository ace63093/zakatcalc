"""Background Geodb Refresh Thread.

Downloads Apple's IP geolocation CSV, stores to R2 (primary) + SQLite (mirror),
and reloads the in-memory GeoIndex. Also backs up visitor logs to R2.

Follows the same pattern as background_sync.py.
"""
import os
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger('geodb_sync')

_refresh_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def start_geodb_refresh():
    """Start the geodb refresh thread if not already running."""
    global _refresh_thread

    from .config import is_geolocation_enabled
    if not is_geolocation_enabled():
        logger.info("Geolocation disabled, skipping geodb refresh thread")
        return

    if _refresh_thread is not None and _refresh_thread.is_alive():
        logger.info("Geodb refresh thread already running")
        return

    _stop_event.clear()
    _refresh_thread = threading.Thread(target=_refresh_loop, daemon=True, name='geodb-refresh')
    _refresh_thread.start()
    logger.info("Geodb refresh thread started")


def stop_geodb_refresh():
    """Stop the geodb refresh thread gracefully."""
    global _refresh_thread

    if _refresh_thread is None:
        return

    logger.info("Stopping geodb refresh thread...")
    _stop_event.set()
    _refresh_thread.join(timeout=5)
    _refresh_thread = None
    logger.info("Geodb refresh thread stopped")


def _refresh_loop():
    """Main refresh loop running in background thread."""
    from .config import get_geodb_refresh_interval_seconds

    data_dir = os.environ.get('DATA_DIR', '/app/data')
    db_path = os.path.join(data_dir, 'pricing.sqlite')
    sleep_seconds = get_geodb_refresh_interval_seconds()

    logger.info(f"Geodb refresh loop started")
    logger.info(f"  DB path: {db_path}")
    logger.info(f"  Refresh interval: {sleep_seconds}s ({sleep_seconds // 3600}h)")

    # Initial delay to let app fully start
    if _stop_event.wait(timeout=15):
        return

    while not _stop_event.is_set():
        try:
            _run_refresh(db_path)
        except Exception as e:
            logger.exception(f"Geodb refresh failed: {e}")

        next_refresh = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
        logger.info(f"Next geodb refresh at {next_refresh.isoformat()}")

        # Check stop event every 30 seconds during sleep
        elapsed = 0
        while elapsed < sleep_seconds and not _stop_event.is_set():
            _stop_event.wait(timeout=30)
            elapsed += 30


def _run_refresh(db_path: str):
    """Execute one geodb refresh cycle."""
    from .geolocation import (
        download_and_parse_apple_geodb,
        store_geodb_to_sqlite,
        store_geodb_to_r2,
        load_geodb_from_sqlite,
        get_geodb_last_updated,
        GeoIndex,
        set_geo_index,
    )
    from .visitor_logging import backup_visitors_to_r2, backfill_visitor_geolocation
    from .r2_client import get_r2_client
    from .r2_config import is_r2_enabled
    from .config import get_geodb_refresh_interval_seconds

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if refresh is needed
    last_updated = get_geodb_last_updated(conn)
    if last_updated:
        try:
            last_dt = datetime.fromisoformat(last_updated)
            age_seconds = (datetime.now() - last_dt).total_seconds()
            interval = get_geodb_refresh_interval_seconds()
            if age_seconds < interval:
                logger.info(f"Geodb still fresh (age: {age_seconds:.0f}s < {interval}s), skipping")
                conn.close()
                return
        except (ValueError, TypeError):
            pass  # Can't parse timestamp, proceed with refresh

    logger.info("Starting geodb refresh...")

    # 1. Download from Apple
    try:
        rows = download_and_parse_apple_geodb()
    except Exception as e:
        logger.error(f"Failed to download Apple geodb: {e}")
        conn.close()
        return

    if not rows:
        logger.warning("Downloaded geodb is empty, skipping update")
        conn.close()
        return

    # 2. Store to R2 (primary)
    r2 = get_r2_client() if is_r2_enabled() else None
    if r2:
        try:
            store_geodb_to_r2(r2, rows)
        except Exception as e:
            logger.warning(f"Failed to store geodb to R2: {e}")

    # 3. Mirror to SQLite
    try:
        store_geodb_to_sqlite(conn, rows)
    except Exception as e:
        logger.error(f"Failed to store geodb to SQLite: {e}")
        conn.close()
        return

    # 4. Reload in-memory index
    index = GeoIndex()
    index.load_from_rows(rows)
    set_geo_index(index)
    logger.info(f"Geodb refresh complete: {index.size} entries loaded")

    # 5. Backfill visitor geo now that index is refreshed, then backup to R2
    try:
        geo_stats = backfill_visitor_geolocation(conn)
        logger.info(
            "Visitor geo backfill: "
            f"status={geo_stats.get('status')} "
            f"scanned={geo_stats.get('scanned', 0)} "
            f"updated={geo_stats.get('updated', 0)}"
        )
    except Exception as e:
        logger.warning(f"Failed to backfill visitor geolocation: {e}")

    if r2:
        try:
            backup_visitors_to_r2(conn, r2)
        except Exception as e:
            logger.warning(f"Failed to backup visitors to R2: {e}")

    conn.close()
