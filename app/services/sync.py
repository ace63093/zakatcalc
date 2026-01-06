"""Pricing data sync service."""
from datetime import date, datetime, timedelta
from typing import Optional

from flask import current_app

from app.db import get_db
from app.services.config import is_sync_enabled, is_auto_sync_enabled
from app.services.providers.registry import get_fx_provider, get_metal_provider, get_crypto_provider
from app.services.providers import ProviderError, RateLimitError, NetworkError


class SyncService:
    """Service for syncing pricing data from external providers."""

    def __init__(self):
        self.fx_provider = get_fx_provider()
        self.metal_provider = get_metal_provider()
        self.crypto_provider = get_crypto_provider()

    def can_sync(self) -> bool:
        """Check if sync is allowed based on configuration."""
        return is_sync_enabled()

    def sync_date(
        self,
        target_date: date,
        types: list[str] | None = None,
        snapshot_type: str = 'daily'
    ) -> dict:
        """Sync pricing data for a single date.

        Args:
            target_date: Date to sync
            types: List of types to sync ('fx', 'metals', 'crypto'). None = all.
            snapshot_type: 'weekly', 'monthly', or 'daily' (default)

        Returns:
            Dict with sync results per type
        """
        if not self.can_sync():
            return {
                'success': False,
                'error': 'Network sync is disabled',
                'message': 'Set PRICING_ALLOW_NETWORK=1 to enable'
            }

        if types is None:
            types = ['fx', 'metals', 'crypto']

        results = {}
        db = get_db()

        if 'fx' in types:
            results['fx'] = self._sync_fx_date(db, target_date, snapshot_type)

        if 'metals' in types:
            results['metals'] = self._sync_metals_date(db, target_date, snapshot_type)

        if 'crypto' in types:
            results['crypto'] = self._sync_crypto_date(db, target_date, snapshot_type)

        db.commit()

        return {
            'success': all(r.get('status') == 'success' for r in results.values()),
            'date': target_date.isoformat(),
            'snapshot_type': snapshot_type,
            'results': results,
            'synced_at': datetime.utcnow().isoformat() + 'Z'
        }

    def sync_range(self, start_date: date, end_date: date, types: list[str] | None = None) -> dict:
        """Sync pricing data for a date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            types: List of types to sync

        Returns:
            Dict with sync results summary
        """
        if not self.can_sync():
            return {
                'success': False,
                'error': 'Network sync is disabled',
                'message': 'Set PRICING_ALLOW_NETWORK=1 to enable'
            }

        if types is None:
            types = ['fx', 'metals', 'crypto']

        results = {t: {'dates_requested': 0, 'dates_synced': 0, 'records_added': 0, 'errors': []} for t in types}

        current = start_date
        while current <= end_date:
            date_results = self.sync_date(current, types)

            for data_type in types:
                type_result = date_results.get('results', {}).get(data_type, {})
                results[data_type]['dates_requested'] += 1
                if type_result.get('status') == 'success':
                    results[data_type]['dates_synced'] += 1
                    results[data_type]['records_added'] += type_result.get('records', 0)
                elif type_result.get('error'):
                    results[data_type]['errors'].append(f"{current}: {type_result['error']}")

            current += timedelta(days=1)

        # Summarize results
        for data_type in results:
            r = results[data_type]
            r['provider'] = getattr(getattr(self, f'{data_type.replace("s", "")}_provider', self.fx_provider), 'name', 'unknown')
            if r['dates_synced'] == r['dates_requested']:
                r['status'] = 'success'
            elif r['dates_synced'] > 0:
                r['status'] = 'partial'
            else:
                r['status'] = 'failed'

        return {
            'success': all(r['status'] in ('success', 'partial') for r in results.values()),
            'sync_results': results,
            'synced_at': datetime.utcnow().isoformat() + 'Z'
        }

    def _sync_fx_date(self, db, target_date: date, snapshot_type: str = 'daily') -> dict:
        """Sync FX rates for a single date."""
        try:
            rates = self.fx_provider.get_rates(target_date)
            if not rates:
                return {'status': 'failed', 'error': 'No rates returned', 'records': 0}

            date_str = target_date.isoformat()
            count = 0

            for rate in rates:
                db.execute('''
                    INSERT OR REPLACE INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (date_str, rate.currency, rate.rate_to_usd, rate.source, snapshot_type))
                count += 1

            # Log the sync
            self._log_sync(db, date_str, 'fx', self.fx_provider.name, 'success', count, snapshot_type=snapshot_type)

            return {'status': 'success', 'records': count, 'provider': self.fx_provider.name}

        except RateLimitError:
            return {'status': 'failed', 'error': 'Rate limit exceeded', 'records': 0}
        except NetworkError as e:
            return {'status': 'failed', 'error': str(e), 'records': 0}
        except ProviderError as e:
            return {'status': 'failed', 'error': str(e), 'records': 0}

    def _sync_metals_date(self, db, target_date: date, snapshot_type: str = 'daily') -> dict:
        """Sync metal prices for a single date."""
        try:
            prices = self.metal_provider.get_prices(target_date)
            if not prices:
                return {'status': 'failed', 'error': 'No prices returned', 'records': 0}

            date_str = target_date.isoformat()
            count = 0

            for price in prices:
                db.execute('''
                    INSERT OR REPLACE INTO metal_prices (date, metal, price_per_gram_usd, source, snapshot_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (date_str, price.metal, price.price_per_gram_usd, price.source, snapshot_type))
                count += 1

            self._log_sync(db, date_str, 'metals', self.metal_provider.name, 'success', count, snapshot_type=snapshot_type)

            return {'status': 'success', 'records': count, 'provider': self.metal_provider.name}

        except RateLimitError:
            return {'status': 'failed', 'error': 'Rate limit exceeded', 'records': 0}
        except NetworkError as e:
            return {'status': 'failed', 'error': str(e), 'records': 0}
        except ProviderError as e:
            return {'status': 'failed', 'error': str(e), 'records': 0}

    def _sync_crypto_date(self, db, target_date: date, snapshot_type: str = 'daily') -> dict:
        """Sync crypto prices for a single date."""
        try:
            prices = self.crypto_provider.get_prices(target_date)
            if not prices:
                return {'status': 'failed', 'error': 'No prices returned', 'records': 0}

            date_str = target_date.isoformat()
            count = 0

            for price in prices:
                db.execute('''
                    INSERT OR REPLACE INTO crypto_prices (date, symbol, name, price_usd, rank, source, snapshot_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (date_str, price.symbol, price.name, price.price_usd, price.rank, price.source, snapshot_type))
                count += 1

                # Also update crypto_assets table
                if price.rank:
                    db.execute('''
                        INSERT OR REPLACE INTO crypto_assets (symbol, name, rank, updated_at)
                        VALUES (?, ?, ?, datetime('now'))
                    ''', (price.symbol, price.name, price.rank))

            self._log_sync(db, date_str, 'crypto', self.crypto_provider.name, 'success', count, snapshot_type=snapshot_type)

            return {'status': 'success', 'records': count, 'provider': self.crypto_provider.name}

        except RateLimitError:
            return {'status': 'failed', 'error': 'Rate limit exceeded', 'records': 0}
        except NetworkError as e:
            return {'status': 'failed', 'error': str(e), 'records': 0}
        except ProviderError as e:
            return {'status': 'failed', 'error': str(e), 'records': 0}

    def _log_sync(
        self,
        db,
        sync_date: str,
        data_type: str,
        provider: str,
        status: str,
        records: int,
        error: str | None = None,
        snapshot_type: str = 'daily'
    ):
        """Log a sync operation."""
        db.execute('''
            INSERT INTO sync_log (sync_date, data_type, provider, status, records_count, error_message, snapshot_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sync_date, data_type, provider, status, records, error, snapshot_type))

    def get_data_coverage(self) -> dict:
        """Get data coverage information from the database.

        Returns coverage for each data type (fx, metals, crypto) and
        cadence-specific counts (daily, weekly, monthly snapshots).
        """
        db = get_db()

        coverage = {}

        # FX coverage
        fx_row = db.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as total_dates
            FROM fx_rates
        ''').fetchone()
        coverage['fx'] = {
            'min_date': fx_row['min_date'],
            'max_date': fx_row['max_date'],
            'total_dates': fx_row['total_dates'] or 0
        }

        # Metals coverage
        metal_row = db.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as total_dates
            FROM metal_prices
        ''').fetchone()
        coverage['metals'] = {
            'min_date': metal_row['min_date'],
            'max_date': metal_row['max_date'],
            'total_dates': metal_row['total_dates'] or 0
        }

        # Crypto coverage
        crypto_row = db.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as total_dates
            FROM crypto_prices
        ''').fetchone()
        coverage['crypto'] = {
            'min_date': crypto_row['min_date'],
            'max_date': crypto_row['max_date'],
            'total_dates': crypto_row['total_dates'] or 0
        }

        # Cadence-specific coverage (3-tier)
        # Daily snapshots
        daily_row = db.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as total_dates
            FROM fx_rates WHERE snapshot_type = 'daily'
        ''').fetchone()
        coverage['daily_snapshots'] = {
            'min_date': daily_row['min_date'],
            'max_date': daily_row['max_date'],
            'total_dates': daily_row['total_dates'] or 0
        }

        # Weekly snapshots
        weekly_row = db.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as total_dates
            FROM fx_rates WHERE snapshot_type = 'weekly'
        ''').fetchone()
        coverage['weekly_snapshots'] = {
            'min_date': weekly_row['min_date'],
            'max_date': weekly_row['max_date'],
            'total_dates': weekly_row['total_dates'] or 0
        }

        # Monthly snapshots
        monthly_row = db.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as total_dates
            FROM fx_rates WHERE snapshot_type = 'monthly'
        ''').fetchone()
        coverage['monthly_snapshots'] = {
            'min_date': monthly_row['min_date'],
            'max_date': monthly_row['max_date'],
            'total_dates': monthly_row['total_dates'] or 0
        }

        return coverage

    def get_daemon_state(self) -> dict | None:
        """Get the current daemon state from the database."""
        db = get_db()
        row = db.execute('SELECT * FROM daemon_state WHERE id = 1').fetchone()
        if row:
            return {
                'last_sync_at': row['last_sync_at'],
                'last_sync_result': row['last_sync_result'],
                'last_error': row['last_error'],
                'next_sync_at': row['next_sync_at'],
                'snapshots_synced': row['snapshots_synced'],
                'updated_at': row['updated_at'],
            }
        return None

    def has_snapshot(self, snapshot_date: date) -> bool:
        """Check if a snapshot exists for the given date."""
        db = get_db()
        date_str = snapshot_date.isoformat()
        row = db.execute(
            'SELECT COUNT(*) as cnt FROM fx_rates WHERE date = ?',
            (date_str,)
        ).fetchone()
        return row['cnt'] > 0


def get_sync_service() -> SyncService:
    """Get a SyncService instance."""
    return SyncService()
