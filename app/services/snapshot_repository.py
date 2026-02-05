"""Unified snapshot repository: SQLite (local) + R2 (remote) + Upstream (providers).

Implements read-through and write-through caching for pricing snapshots.
"""
import logging
from datetime import date
from typing import Any

from app.db import get_db
from .r2_client import R2Client, get_r2_client
from .db_pricing import (
    get_fx_snapshot,
    get_metal_snapshot,
    get_crypto_snapshot,
)

logger = logging.getLogger(__name__)


class SnapshotRepository:
    """Unified snapshot access with fallback chain.

    Lookup order for ensure_snapshot():
    1. SQLite (fast local cache)
    2. R2 (shared remote cache)
    3. Upstream provider (network fetch)

    Each successful fetch populates lower-tier caches.
    """

    def __init__(
        self,
        r2_client: R2Client | None = None,
        sync_service: Any | None = None,
        allow_network: bool = False,
    ):
        """Initialize repository.

        Args:
            r2_client: R2 client (None to use auto-detected or disable R2)
            sync_service: SyncService for upstream fetches (None to disable upstream)
            allow_network: Whether upstream network fetches are allowed
        """
        self._r2 = r2_client
        self._sync_service = sync_service
        self._allow_network = allow_network

    def ensure_fx_snapshot(
        self,
        effective_date: date,
        cadence: str,
        db=None,
    ) -> dict | None:
        """Ensure FX snapshot exists, trying all sources.

        Args:
            effective_date: The snapshot date to ensure
            cadence: 'daily', 'weekly', or 'monthly'
            db: Optional database connection (uses get_db() if None)

        Returns:
            FX rates dict {currency: rate_to_usd} or None if all sources fail
        """
        date_str = effective_date.isoformat() if isinstance(effective_date, date) else effective_date

        # 1. Check SQLite
        local_effective, local_data = get_fx_snapshot(date_str)
        if local_data and local_effective == date_str:
            logger.debug(f"FX snapshot {date_str} found in SQLite")
            return local_data

        # 2. Check R2
        if self._r2:
            try:
                r2_data = self._r2.get_snapshot('fx', cadence, effective_date)
                if r2_data and 'data' in r2_data:
                    logger.info(f"FX snapshot {date_str} found in R2, caching to SQLite")
                    # Write to SQLite
                    source = r2_data.get('source', 'r2')
                    self._store_fx_to_sqlite(date_str, r2_data['data'], source, cadence, db)
                    return r2_data['data']
            except Exception as e:
                logger.warning(f"R2 lookup failed for FX {date_str}: {e}")

        # 3. Fetch from upstream
        if self._allow_network and self._sync_service:
            try:
                logger.info(f"Fetching FX {date_str} from upstream provider")
                result = self._sync_fx_from_upstream(effective_date, cadence, db)
                if result:
                    # Mirror to R2
                    self._mirror_fx_to_r2(effective_date, cadence, result)
                    return result
            except Exception as e:
                logger.warning(f"Upstream fetch failed for FX {date_str}: {e}")

        logger.warning(f"All sources failed for FX {date_str}")
        return None

    def ensure_metals_snapshot(
        self,
        effective_date: date,
        cadence: str,
        db=None,
    ) -> dict | None:
        """Ensure metals snapshot exists.

        Args:
            effective_date: The snapshot date to ensure
            cadence: 'daily', 'weekly', or 'monthly'
            db: Optional database connection

        Returns:
            Metals dict {metal: price_per_gram} or None if all sources fail
        """
        date_str = effective_date.isoformat() if isinstance(effective_date, date) else effective_date

        # 1. Check SQLite
        local_effective, local_data = get_metal_snapshot(date_str)
        if local_data and local_effective == date_str:
            logger.debug(f"Metals snapshot {date_str} found in SQLite")
            return local_data

        # 2. Check R2
        if self._r2:
            try:
                r2_data = self._r2.get_snapshot('metals', cadence, effective_date)
                if r2_data and 'data' in r2_data:
                    logger.info(f"Metals snapshot {date_str} found in R2")
                    source = r2_data.get('source', 'r2')
                    self._store_metals_to_sqlite(date_str, r2_data['data'], source, cadence, db)
                    return r2_data['data']
            except Exception as e:
                logger.warning(f"R2 lookup failed for metals {date_str}: {e}")

        # 3. Fetch from upstream
        if self._allow_network and self._sync_service:
            try:
                logger.info(f"Fetching metals {date_str} from upstream")
                result = self._sync_metals_from_upstream(effective_date, cadence, db)
                if result:
                    self._mirror_metals_to_r2(effective_date, cadence, result)
                    return result
            except Exception as e:
                logger.warning(f"Upstream fetch failed for metals {date_str}: {e}")

        return None

    def ensure_crypto_snapshot(
        self,
        effective_date: date,
        cadence: str,
        db=None,
    ) -> dict | None:
        """Ensure crypto snapshot exists.

        Args:
            effective_date: The snapshot date to ensure
            cadence: 'daily', 'weekly', or 'monthly'
            db: Optional database connection

        Returns:
            Crypto dict {symbol: {name, price, rank}} or None if all sources fail
        """
        date_str = effective_date.isoformat() if isinstance(effective_date, date) else effective_date

        # 1. Check SQLite
        local_effective, local_data = get_crypto_snapshot(date_str)
        if local_data and local_effective == date_str:
            logger.debug(f"Crypto snapshot {date_str} found in SQLite")
            return local_data

        # 2. Check R2
        if self._r2:
            try:
                r2_data = self._r2.get_snapshot('crypto', cadence, effective_date)
                if r2_data and 'data' in r2_data:
                    logger.info(f"Crypto snapshot {date_str} found in R2")
                    source = r2_data.get('source', 'r2')
                    self._store_crypto_to_sqlite(date_str, r2_data['data'], source, cadence, db)
                    return r2_data['data']
            except Exception as e:
                logger.warning(f"R2 lookup failed for crypto {date_str}: {e}")

        # 3. Fetch from upstream
        if self._allow_network and self._sync_service:
            try:
                logger.info(f"Fetching crypto {date_str} from upstream")
                result = self._sync_crypto_from_upstream(effective_date, cadence, db)
                if result:
                    self._mirror_crypto_to_r2(effective_date, cadence, result)
                    return result
            except Exception as e:
                logger.warning(f"Upstream fetch failed for crypto {date_str}: {e}")

        return None

    # Helper methods for SQLite storage
    def _store_fx_to_sqlite(self, date_str, data, source, cadence, db):
        """Store FX rates to SQLite."""
        try:
            if db is None:
                db = get_db()
            for currency, rate in data.items():
                db.execute('''
                    INSERT OR REPLACE INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (date_str, currency, rate, source, cadence))
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to store FX to SQLite: {e}")

    def _store_metals_to_sqlite(self, date_str, data, source, cadence, db):
        """Store metals to SQLite."""
        try:
            if db is None:
                db = get_db()
            for metal, price in data.items():
                db.execute('''
                    INSERT OR REPLACE INTO metal_prices (date, metal, price_per_gram_usd, source, snapshot_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (date_str, metal, price, source, cadence))
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to store metals to SQLite: {e}")

    def _store_crypto_to_sqlite(self, date_str, data, source, cadence, db):
        """Store crypto to SQLite."""
        try:
            if db is None:
                db = get_db()
            for symbol, info in data.items():
                db.execute('''
                    INSERT OR REPLACE INTO crypto_prices (date, symbol, name, price_usd, rank, source, snapshot_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (date_str, symbol, info.get('name', symbol), info.get('price', 0), info.get('rank', 0), source, cadence))
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to store crypto to SQLite: {e}")

    # Helper methods for upstream fetches
    def _sync_fx_from_upstream(self, effective_date, cadence, db):
        """Sync FX from upstream provider and return data."""
        if not self._sync_service:
            return None

        result = self._sync_service.sync_date(
            effective_date,
            types=['fx'],
            snapshot_type=cadence
        )

        if result.get('success') and result.get('results', {}).get('fx', {}).get('status') == 'success':
            # Re-fetch from SQLite after sync
            _, data = get_fx_snapshot(effective_date.isoformat())
            return data
        return None

    def _sync_metals_from_upstream(self, effective_date, cadence, db):
        """Sync metals from upstream provider and return data."""
        if not self._sync_service:
            return None

        result = self._sync_service.sync_date(
            effective_date,
            types=['metals'],
            snapshot_type=cadence
        )

        if result.get('success') and result.get('results', {}).get('metals', {}).get('status') == 'success':
            _, data = get_metal_snapshot(effective_date.isoformat())
            return data
        return None

    def _sync_crypto_from_upstream(self, effective_date, cadence, db):
        """Sync crypto from upstream provider and return data."""
        if not self._sync_service:
            return None

        result = self._sync_service.sync_date(
            effective_date,
            types=['crypto'],
            snapshot_type=cadence
        )

        if result.get('success') and result.get('results', {}).get('crypto', {}).get('status') == 'success':
            _, data = get_crypto_snapshot(effective_date.isoformat())
            return data
        return None

    # Helper method for R2 mirroring
    def _mirror_to_r2(self, snapshot_type: str, effective_date, cadence, data):
        """Mirror snapshot to R2 (best-effort).

        Args:
            snapshot_type: 'fx', 'metals', or 'crypto'
            effective_date: Date of the snapshot
            cadence: 'daily', 'weekly', or 'monthly'
            data: Snapshot data to mirror
        """
        if not self._r2:
            return
        try:
            self._r2.put_snapshot(snapshot_type, cadence, effective_date, {
                'source': 'upstream',
                'data': data,
            })
        except Exception as e:
            logger.warning(f"Failed to mirror {snapshot_type} to R2: {e}")

    # Thin wrappers for backward compatibility
    def _mirror_fx_to_r2(self, effective_date, cadence, data):
        self._mirror_to_r2('fx', effective_date, cadence, data)

    def _mirror_metals_to_r2(self, effective_date, cadence, data):
        self._mirror_to_r2('metals', effective_date, cadence, data)

    def _mirror_crypto_to_r2(self, effective_date, cadence, data):
        self._mirror_to_r2('crypto', effective_date, cadence, data)


def get_snapshot_repository(
    allow_network: bool = False,
    sync_service: Any = None,
) -> SnapshotRepository:
    """Factory function for SnapshotRepository.

    Args:
        allow_network: Whether upstream network fetches are allowed
        sync_service: SyncService for upstream fetches (None to disable upstream)

    Returns:
        Configured SnapshotRepository instance
    """
    return SnapshotRepository(
        r2_client=get_r2_client(),
        sync_service=sync_service,
        allow_network=allow_network,
    )
