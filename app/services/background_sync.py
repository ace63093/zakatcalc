"""
Background Pricing Sync Thread

Runs pricing sync in-process as a background thread when the web app starts.
Used for single-container deployments (like DigitalOcean App Platform).

This is a lightweight alternative to running pricing_sync_daemon.py as a
separate container/process.
"""

import os
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger('background_sync')

# Global to track if sync thread is running
_sync_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def start_background_sync():
    """Start the background sync thread if not already running.

    Should be called once when the Flask app starts.
    Only runs if PRICING_AUTO_SYNC=1 (default).
    """
    global _sync_thread

    auto_sync = os.environ.get('PRICING_AUTO_SYNC', '1')
    if auto_sync.lower() not in ('1', 'true', 'yes'):
        logger.info("Background sync disabled (PRICING_AUTO_SYNC != 1)")
        return

    if _sync_thread is not None and _sync_thread.is_alive():
        logger.info("Background sync thread already running")
        return

    _stop_event.clear()
    _sync_thread = threading.Thread(target=_sync_loop, daemon=True, name='pricing-sync')
    _sync_thread.start()
    logger.info("Background sync thread started")


def stop_background_sync():
    """Stop the background sync thread gracefully."""
    global _sync_thread

    if _sync_thread is None:
        return

    logger.info("Stopping background sync thread...")
    _stop_event.set()
    _sync_thread.join(timeout=5)
    _sync_thread = None
    logger.info("Background sync thread stopped")


def _sync_loop():
    """Main sync loop that runs in background thread."""
    data_dir = os.environ.get('DATA_DIR', '/app/data')
    db_path = os.path.join(data_dir, 'pricing.sqlite')
    sleep_seconds = int(os.environ.get('PRICING_SYNC_INTERVAL_SECONDS', '21600'))

    logger.info(f"Background sync loop started")
    logger.info(f"  DB path: {db_path}")
    logger.info(f"  Sync interval: {sleep_seconds}s ({sleep_seconds // 3600}h)")

    # Initial delay to let app fully start
    if _stop_event.wait(timeout=10):
        return

    while not _stop_event.is_set():
        try:
            _run_sync_cycle(db_path)
        except Exception as e:
            logger.exception(f"Sync cycle failed: {e}")

        # Sleep with periodic checks for stop signal
        next_sync = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
        logger.info(f"Next sync at {next_sync.isoformat()}")

        # Check stop event every 30 seconds during sleep
        elapsed = 0
        while elapsed < sleep_seconds and not _stop_event.is_set():
            _stop_event.wait(timeout=30)
            elapsed += 30


def _run_sync_cycle(db_path: str):
    """Execute one sync cycle."""
    from app.services.snapshot_repository import get_snapshot_repository
    from app.services.sync import SyncService
    from app.services.cadence import get_all_required_snapshots
    from app.services.time_provider import get_today

    logger.info("Starting background sync cycle")

    today = get_today()
    monthly_limit_str = os.environ.get('PRICING_MONTHLY_LIMIT', '')
    monthly_limit = int(monthly_limit_str) if monthly_limit_str else None

    required_snapshots = get_all_required_snapshots(
        today=today,
        include_monthly=True,
        monthly_limit=monthly_limit
    )

    # Find missing snapshots
    conn = sqlite3.connect(db_path)
    missing = []
    for snapshot_date, cadence in required_snapshots:
        date_str = snapshot_date.isoformat()
        cursor = conn.execute('SELECT COUNT(*) FROM fx_rates WHERE date = ?', (date_str,))
        if cursor.fetchone()[0] == 0:
            missing.append((snapshot_date, cadence))
    conn.close()

    logger.info(f"Required: {len(required_snapshots)}, Missing: {len(missing)}")

    if not missing:
        logger.info("All snapshots present")
        return

    # Sync missing snapshots
    sync_service = SyncService()
    repo = get_snapshot_repository(allow_network=True, sync_service=sync_service)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    synced = 0

    for snapshot_date, cadence in missing:
        if _stop_event.is_set():
            break

        try:
            logger.info(f"Syncing {snapshot_date} ({cadence})...")
            fx_ok = repo.ensure_fx_snapshot(snapshot_date, cadence, db=conn)
            metals_ok = repo.ensure_metals_snapshot(snapshot_date, cadence, db=conn)
            crypto_ok = repo.ensure_crypto_snapshot(snapshot_date, cadence, db=conn)

            if fx_ok or metals_ok or crypto_ok:
                synced += 1
        except Exception as e:
            logger.error(f"Failed {snapshot_date}: {e}")

    conn.close()
    logger.info(f"Sync cycle complete: {synced}/{len(missing)} synced")
