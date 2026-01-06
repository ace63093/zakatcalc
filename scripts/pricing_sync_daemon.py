#!/usr/bin/env python3
"""
Pricing Sync Daemon

Background service that maintains pricing snapshots using 3-tier cadence:
- DAILY snapshots for last 30 days (days 0-29)
- WEEKLY snapshots (Mondays) for days 30-89
- MONTHLY snapshots (1st of month) from 2000-01-01 to day 90+

Runs on a configurable interval (default: 6 hours).

Usage:
    python scripts/pricing_sync_daemon.py

Environment Variables:
    DATA_DIR: Path to data directory (default: /app/data)
    PRICING_ALLOW_NETWORK: Must be '1' to enable sync (default: 1)
    PRICING_SYNC_INTERVAL_SECONDS: Sleep between cycles (default: 21600 = 6 hours)
    PRICING_MONTHLY_LIMIT: Max months of historical monthly snapshots (default: None = all)
"""

import os
import sys
import time
import sqlite3
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pricing_daemon')

DAEMON_VERSION = '2.0.0'  # 3-tier cadence


class PricingSyncDaemon:
    """Daemon for maintaining pricing snapshots using 3-tier cadence."""

    def __init__(self):
        self.data_dir = os.environ.get('DATA_DIR', '/app/data')
        self.db_path = os.path.join(self.data_dir, 'pricing.sqlite')
        self.sleep_seconds = int(os.environ.get('PRICING_SYNC_INTERVAL_SECONDS', '21600'))
        monthly_limit_str = os.environ.get('PRICING_MONTHLY_LIMIT', '')
        self.monthly_limit = int(monthly_limit_str) if monthly_limit_str else None

    def run(self):
        """Main daemon loop."""
        from app.services.cadence import DAILY_WINDOW_DAYS, WEEKLY_WINDOW_DAYS, MONTHLY_START

        logger.info(f"Starting pricing sync daemon v{DAEMON_VERSION}")
        logger.info(f"  Data dir: {self.data_dir}")
        logger.info(f"  DB path: {self.db_path}")
        logger.info(f"  Sync interval: {self.sleep_seconds}s ({self.sleep_seconds // 3600}h)")
        logger.info(f"  Cadence: daily={DAILY_WINDOW_DAYS}d, weekly={WEEKLY_WINDOW_DAYS}d, monthly from {MONTHLY_START}")
        if self.monthly_limit:
            logger.info(f"  Monthly limit: {self.monthly_limit} months")

        # Ensure database exists
        self.ensure_database()

        while True:
            try:
                self.sync_cycle()
            except Exception as e:
                logger.exception(f"Sync cycle failed: {e}")
                self.update_state('failed', str(e), 0)

            next_sync = datetime.now(timezone.utc) + timedelta(seconds=self.sleep_seconds)
            logger.info(f"Sleeping until {next_sync.isoformat()}")
            time.sleep(self.sleep_seconds)

    def ensure_database(self):
        """Ensure database exists with proper schema."""
        os.makedirs(self.data_dir, exist_ok=True)

        if not os.path.exists(self.db_path):
            logger.info("Creating new database...")
            from app.db import get_schema
            conn = sqlite3.connect(self.db_path)
            conn.executescript(get_schema())
            conn.commit()
            conn.close()
            logger.info("Database created")

    def sync_cycle(self):
        """Execute one sync cycle.

        Uses SnapshotRepository to check SQLite -> R2 -> upstream,
        ensuring we don't hit upstream providers unnecessarily.
        """
        from app.services.snapshot_repository import get_snapshot_repository
        from app.services.sync import SyncService

        logger.info("=" * 50)
        logger.info("Starting sync cycle")

        required_snapshots = self.calculate_required_snapshots()

        # Count by cadence type
        cadence_counts = {'daily': 0, 'weekly': 0, 'monthly': 0}
        for _, cadence in required_snapshots:
            cadence_counts[cadence] = cadence_counts.get(cadence, 0) + 1

        logger.info(f"Required snapshots: {len(required_snapshots)} total "
                    f"(daily={cadence_counts['daily']}, weekly={cadence_counts['weekly']}, "
                    f"monthly={cadence_counts['monthly']})")

        missing = self.find_missing_snapshots(required_snapshots)

        # Count missing by cadence
        missing_counts = {'daily': 0, 'weekly': 0, 'monthly': 0}
        for _, cadence in missing:
            missing_counts[cadence] = missing_counts.get(cadence, 0) + 1

        logger.info(f"Missing snapshots: {len(missing)} "
                    f"(daily={missing_counts['daily']}, weekly={missing_counts['weekly']}, "
                    f"monthly={missing_counts['monthly']})")

        if not missing:
            logger.info("All snapshots present, nothing to sync")
            self.update_state('success', None, 0)
            return

        # Create repository with upstream fetch capability
        # This will check SQLite -> R2 -> upstream for each missing snapshot
        sync_service = SyncService()
        repo = get_snapshot_repository(allow_network=True, sync_service=sync_service)

        # Sync missing snapshots using repository
        synced = 0
        errors = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        for snapshot_date, cadence in missing:
            try:
                logger.info(f"Ensuring {snapshot_date} ({cadence}) via repository...")
                # Repository will check SQLite -> R2 -> upstream
                # If found in R2, it populates SQLite automatically
                fx_ok = repo.ensure_fx_snapshot(snapshot_date, cadence, db=conn)
                metals_ok = repo.ensure_metals_snapshot(snapshot_date, cadence, db=conn)
                crypto_ok = repo.ensure_crypto_snapshot(snapshot_date, cadence, db=conn)

                if fx_ok or metals_ok or crypto_ok:
                    synced += 1
                    logger.info(f"  Ensured: fx={bool(fx_ok)}, metals={bool(metals_ok)}, crypto={bool(crypto_ok)}")
                else:
                    error_msg = f"{snapshot_date}: All sources failed"
                    errors.append(error_msg)
                    logger.warning(f"  All sources failed for {snapshot_date}")

            except Exception as e:
                error_msg = f"{snapshot_date}: {e}"
                errors.append(error_msg)
                logger.error(f"Failed to ensure {snapshot_date}: {e}")

        conn.close()

        # Update state
        if not errors:
            status = 'success'
        elif synced > 0:
            status = 'partial'
        else:
            status = 'failed'

        error_summary = '; '.join(errors[:5]) if errors else None
        self.update_state(status, error_summary, synced)

        logger.info(f"Sync cycle complete: {synced} synced, {len(errors)} errors")

    def calculate_required_snapshots(self) -> list[tuple[date, str]]:
        """Calculate all required snapshot dates using 3-tier cadence.

        Returns:
            List of (date, cadence_type) tuples where cadence_type is
            'daily', 'weekly', or 'monthly'.
        """
        from app.services.cadence import get_all_required_snapshots
        from app.services.time_provider import get_today

        today = get_today()
        return get_all_required_snapshots(
            today=today,
            include_monthly=True,
            monthly_limit=self.monthly_limit
        )

    def find_missing_snapshots(self, required: list[tuple[date, str]]) -> list[tuple[date, str]]:
        """Find snapshots that don't exist in database."""
        conn = sqlite3.connect(self.db_path)
        missing = []

        for snapshot_date, cadence in required:
            date_str = snapshot_date.isoformat()
            cursor = conn.execute(
                'SELECT COUNT(*) FROM fx_rates WHERE date = ?',
                (date_str,)
            )
            if cursor.fetchone()[0] == 0:
                missing.append((snapshot_date, cadence))

        conn.close()
        return missing

    def sync_snapshot(self, snapshot_date: date, cadence: str):
        """Sync a single snapshot date."""
        from app.services.providers.registry import (
            get_fx_provider,
            get_metal_provider,
            get_crypto_provider
        )
        from app.services.providers import ProviderError

        conn = sqlite3.connect(self.db_path)
        date_str = snapshot_date.isoformat()
        results = {'fx': False, 'metals': False, 'crypto': False}

        try:
            # Sync FX
            try:
                fx_provider = get_fx_provider()
                rates = fx_provider.get_rates(snapshot_date)
                for rate in rates:
                    conn.execute('''
                        INSERT OR REPLACE INTO fx_rates
                        (date, currency, rate_to_usd, source, snapshot_type)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (date_str, rate.currency, rate.rate_to_usd, rate.source, cadence))
                results['fx'] = True
                logger.info(f"  FX: {len(rates)} rates")
            except ProviderError as e:
                logger.warning(f"  FX failed: {e}")

            # Sync metals
            try:
                metal_provider = get_metal_provider()
                prices = metal_provider.get_prices(snapshot_date)
                for price in prices:
                    conn.execute('''
                        INSERT OR REPLACE INTO metal_prices
                        (date, metal, price_per_gram_usd, source, snapshot_type)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (date_str, price.metal, price.price_per_gram_usd, price.source, cadence))
                results['metals'] = True
                logger.info(f"  Metals: {len(prices)} prices")
            except ProviderError as e:
                logger.warning(f"  Metals failed: {e}")

            # Sync crypto
            try:
                crypto_provider = get_crypto_provider()
                crypto_prices = crypto_provider.get_prices(snapshot_date)
                for cp in crypto_prices:
                    conn.execute('''
                        INSERT OR REPLACE INTO crypto_prices
                        (date, symbol, name, price_usd, rank, source, snapshot_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (date_str, cp.symbol, cp.name, cp.price_usd, cp.rank, cp.source, cadence))

                    # Update crypto_assets table
                    if cp.rank:
                        conn.execute('''
                            INSERT OR REPLACE INTO crypto_assets (symbol, name, rank, updated_at)
                            VALUES (?, ?, ?, datetime('now'))
                        ''', (cp.symbol, cp.name, cp.rank))
                results['crypto'] = True
                logger.info(f"  Crypto: {len(crypto_prices)} prices")
            except ProviderError as e:
                logger.warning(f"  Crypto failed: {e}")

            # Log sync operation
            status = 'success' if all(results.values()) else 'partial'
            conn.execute('''
                INSERT INTO sync_log (sync_date, data_type, provider, status, records_count, snapshot_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (date_str, 'all', 'daemon', status, 1, cadence))

            conn.commit()

            if not any(results.values()):
                raise ProviderError("All providers failed")

        finally:
            conn.close()

    def update_state(self, result: str, error: Optional[str], snapshots_synced: int):
        """Update daemon state in database."""
        conn = sqlite3.connect(self.db_path)
        next_sync = (datetime.now(timezone.utc) + timedelta(seconds=self.sleep_seconds)).isoformat()

        conn.execute('''
            INSERT OR REPLACE INTO daemon_state
            (id, last_sync_at, last_sync_result, last_error, next_sync_at, snapshots_synced, daemon_version, updated_at)
            VALUES (1, datetime('now'), ?, ?, ?, ?, ?, datetime('now'))
        ''', (result, error, next_sync, snapshots_synced, DAEMON_VERSION))
        conn.commit()
        conn.close()


def main():
    """Entry point."""
    # Check prerequisites
    allow_network = os.environ.get('PRICING_ALLOW_NETWORK', '1')
    if allow_network.lower() not in ('1', 'true', 'yes'):
        logger.error("PRICING_ALLOW_NETWORK must be set to '1' to run daemon")
        logger.error(f"Current value: {allow_network}")
        sys.exit(1)

    daemon = PricingSyncDaemon()
    daemon.run()


if __name__ == '__main__':
    main()
