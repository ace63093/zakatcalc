"""Tests for SnapshotRepository - no network calls."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.snapshot_repository import SnapshotRepository, get_snapshot_repository
from tests.fakes.fake_r2 import FakeR2
from app.services.r2_client import R2Client


@pytest.fixture
def fake_r2():
    """Provide FakeR2 instance."""
    return FakeR2()


@pytest.fixture
def r2_client(fake_r2, monkeypatch):
    """Provide R2Client with fake backend."""
    monkeypatch.setenv('R2_ENABLED', '1')
    monkeypatch.setenv('R2_BUCKET', 'test-bucket')
    monkeypatch.setenv('R2_ENDPOINT_URL', 'https://fake.r2.dev')
    monkeypatch.setenv('R2_ACCESS_KEY_ID', 'fake-key')
    monkeypatch.setenv('R2_SECRET_ACCESS_KEY', 'fake-secret')
    monkeypatch.setenv('R2_PREFIX', '')
    return R2Client(s3_client=fake_r2)


@pytest.fixture
def mock_sync_service():
    """Provide mock SyncService."""
    sync = MagicMock()
    sync.can_sync.return_value = True
    return sync


class TestEnsureFxSnapshotSqliteFirst:
    """Test SQLite-first lookup behavior."""

    def test_ensure_fx_returns_sqlite_first(self, db_app, r2_client, mock_sync_service):
        """SQLite hit returns data without calling R2 or upstream."""
        with db_app.app_context():
            # Seed SQLite with test data
            from app.db import get_db
            db = get_db()
            db.execute(
                'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                ('2026-01-06', 'EUR', 0.91, 'test', 'daily')
            )
            db.execute(
                'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                ('2026-01-06', 'CAD', 1.38, 'test', 'daily')
            )
            db.commit()

            repo = SnapshotRepository(
                r2_client=r2_client,
                sync_service=mock_sync_service,
                allow_network=True,
            )

            result = repo.ensure_fx_snapshot(date(2026, 1, 6), 'daily')

            assert result is not None
            # Cross-rates are computed from USD base
            assert 'EUR' in result
            assert 'CAD' in result
            # SyncService should NOT be called since SQLite had data
            mock_sync_service.sync_date.assert_not_called()

    def test_ensure_metals_returns_sqlite_first(self, db_app, r2_client):
        """SQLite hit for metals returns data without R2."""
        with db_app.app_context():
            from app.db import get_db
            db = get_db()
            db.execute(
                'INSERT INTO metal_prices (date, metal, price_per_gram_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                ('2026-01-06', 'gold', 85.0, 'test', 'daily')
            )
            db.commit()

            repo = SnapshotRepository(r2_client=r2_client, sync_service=None, allow_network=False)
            result = repo.ensure_metals_snapshot(date(2026, 1, 6), 'daily')

            assert result is not None
            assert 'gold' in result

    def test_ensure_crypto_returns_sqlite_first(self, db_app, r2_client):
        """SQLite hit for crypto returns data without R2."""
        with db_app.app_context():
            from app.db import get_db
            db = get_db()
            db.execute(
                '''INSERT INTO crypto_prices (date, symbol, name, price_usd, rank, source, snapshot_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('2026-01-06', 'BTC', 'Bitcoin', 100000.0, 1, 'test', 'daily')
            )
            db.commit()

            repo = SnapshotRepository(r2_client=r2_client, sync_service=None, allow_network=False)
            result = repo.ensure_crypto_snapshot(date(2026, 1, 6), 'daily')

            assert result is not None
            assert 'BTC' in result


class TestEnsureFxFallbackToR2:
    """Test R2 fallback when SQLite misses."""

    def test_ensure_fx_falls_back_to_r2(self, db_app, r2_client, mock_sync_service):
        """SQLite miss, R2 hit writes to SQLite and returns data."""
        with db_app.app_context():
            # Pre-populate R2 with test data
            r2_client.put_snapshot('fx', 'daily', date(2026, 1, 7), {
                'source': 'r2-test',
                'data': {'EUR': 0.91, 'CAD': 1.38, 'USD': 1.0},
            })

            repo = SnapshotRepository(
                r2_client=r2_client,
                sync_service=mock_sync_service,
                allow_network=True,
            )

            result = repo.ensure_fx_snapshot(date(2026, 1, 7), 'daily')

            assert result is not None
            assert result['EUR'] == 0.91
            assert result['CAD'] == 1.38
            # Upstream should NOT be called since R2 had data
            mock_sync_service.sync_date.assert_not_called()

            # Verify data was cached to SQLite
            from app.db import get_db
            db = get_db()
            rows = db.execute(
                'SELECT currency, rate_to_usd FROM fx_rates WHERE date = ?',
                ('2026-01-07',)
            ).fetchall()
            currencies = {r['currency']: r['rate_to_usd'] for r in rows}
            assert currencies.get('EUR') == 0.91

    def test_ensure_metals_falls_back_to_r2(self, db_app, r2_client):
        """SQLite miss for metals, R2 hit returns data."""
        with db_app.app_context():
            r2_client.put_snapshot('metals', 'weekly', date(2025, 12, 30), {
                'source': 'r2-test',
                'data': {'gold': 85.0, 'silver': 1.05},
            })

            repo = SnapshotRepository(r2_client=r2_client, sync_service=None, allow_network=False)
            result = repo.ensure_metals_snapshot(date(2025, 12, 30), 'weekly')

            assert result is not None
            assert result['gold'] == 85.0

    def test_ensure_crypto_falls_back_to_r2(self, db_app, r2_client):
        """SQLite miss for crypto, R2 hit returns data."""
        with db_app.app_context():
            # Use a date not seeded in db_app fixture (which seeds 2025-01-01)
            r2_client.put_snapshot('crypto', 'monthly', date(2025, 2, 1), {
                'source': 'r2-test',
                'data': {
                    'BTC': {'name': 'Bitcoin', 'price': 100000.0, 'rank': 1},
                    'ETH': {'name': 'Ethereum', 'price': 4000.0, 'rank': 2},
                },
            })

            repo = SnapshotRepository(r2_client=r2_client, sync_service=None, allow_network=False)
            result = repo.ensure_crypto_snapshot(date(2025, 2, 1), 'monthly')

            assert result is not None
            assert result['BTC']['price'] == 100000.0


class TestEnsureFxFallbackToUpstream:
    """Test upstream fallback when SQLite and R2 miss."""

    def test_ensure_fx_falls_back_to_upstream(self, db_app, r2_client, mock_sync_service):
        """SQLite miss, R2 miss, upstream hit returns data."""
        with db_app.app_context():
            # Configure mock to simulate successful sync
            mock_sync_service.sync_date.return_value = {
                'success': True,
                'results': {
                    'fx': {'status': 'success', 'records': 3}
                }
            }

            # After sync, we need data in SQLite for re-fetch
            from app.db import get_db
            def side_effect(*args, **kwargs):
                db = get_db()
                db.execute(
                    'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                    ('2026-01-08', 'EUR', 0.92, 'upstream', 'daily')
                )
                db.execute(
                    'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                    ('2026-01-08', 'USD', 1.0, 'upstream', 'daily')
                )
                db.commit()
                return mock_sync_service.sync_date.return_value

            mock_sync_service.sync_date.side_effect = side_effect

            repo = SnapshotRepository(
                r2_client=r2_client,
                sync_service=mock_sync_service,
                allow_network=True,
            )

            result = repo.ensure_fx_snapshot(date(2026, 1, 8), 'daily')

            assert result is not None
            assert 'EUR' in result
            # Verify sync was called
            mock_sync_service.sync_date.assert_called_once()


class TestAllSourcesFail:
    """Test behavior when all sources fail."""

    def test_ensure_fx_all_fail_returns_none(self, db_app, r2_client, mock_sync_service):
        """All sources fail returns None."""
        with db_app.app_context():
            # No SQLite data
            # No R2 data
            # Upstream fails
            mock_sync_service.sync_date.return_value = {
                'success': False,
                'results': {
                    'fx': {'status': 'failed', 'error': 'Network error'}
                }
            }

            repo = SnapshotRepository(
                r2_client=r2_client,
                sync_service=mock_sync_service,
                allow_network=True,
            )

            result = repo.ensure_fx_snapshot(date(2030, 1, 1), 'daily')

            assert result is None

    def test_ensure_metals_all_fail_returns_none(self, db_app, r2_client):
        """Metals with no sources returns None."""
        with db_app.app_context():
            repo = SnapshotRepository(r2_client=r2_client, sync_service=None, allow_network=False)
            result = repo.ensure_metals_snapshot(date(2030, 1, 1), 'daily')
            assert result is None


class TestR2Disabled:
    """Test behavior when R2 is disabled."""

    def test_r2_disabled_skips_remote(self, db_app, mock_sync_service):
        """R2=None skips R2 check and goes to upstream."""
        with db_app.app_context():
            mock_sync_service.sync_date.return_value = {
                'success': True,
                'results': {'fx': {'status': 'success', 'records': 2}}
            }

            from app.db import get_db
            def side_effect(*args, **kwargs):
                db = get_db()
                db.execute(
                    'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                    ('2026-01-09', 'EUR', 0.90, 'upstream', 'daily')
                )
                db.execute(
                    'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                    ('2026-01-09', 'USD', 1.0, 'upstream', 'daily')
                )
                db.commit()
                return mock_sync_service.sync_date.return_value

            mock_sync_service.sync_date.side_effect = side_effect

            # No R2 client
            repo = SnapshotRepository(
                r2_client=None,
                sync_service=mock_sync_service,
                allow_network=True,
            )

            result = repo.ensure_fx_snapshot(date(2026, 1, 9), 'daily')

            assert result is not None
            # Upstream should be called since R2 was skipped
            mock_sync_service.sync_date.assert_called_once()


class TestNetworkDisabled:
    """Test behavior when network is disabled."""

    def test_network_disabled_skips_upstream(self, db_app, r2_client, mock_sync_service):
        """allow_network=False skips upstream even with sync_service."""
        with db_app.app_context():
            # No SQLite data
            # No R2 data

            repo = SnapshotRepository(
                r2_client=r2_client,
                sync_service=mock_sync_service,
                allow_network=False,  # Disabled!
            )

            result = repo.ensure_fx_snapshot(date(2030, 5, 5), 'daily')

            # Should return None (no data)
            assert result is None
            # Sync should NOT be called
            mock_sync_service.sync_date.assert_not_called()


class TestR2Mirroring:
    """Test that upstream fetches are mirrored to R2."""

    def test_upstream_result_mirrored_to_r2(self, db_app, r2_client, fake_r2, mock_sync_service):
        """Successful upstream fetch mirrors data to R2."""
        with db_app.app_context():
            mock_sync_service.sync_date.return_value = {
                'success': True,
                'results': {'fx': {'status': 'success', 'records': 2}}
            }

            from app.db import get_db
            def side_effect(*args, **kwargs):
                db = get_db()
                db.execute(
                    'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                    ('2026-01-10', 'GBP', 0.78, 'upstream', 'daily')
                )
                db.execute(
                    'INSERT INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type) VALUES (?, ?, ?, ?, ?)',
                    ('2026-01-10', 'USD', 1.0, 'upstream', 'daily')
                )
                db.commit()
                return mock_sync_service.sync_date.return_value

            mock_sync_service.sync_date.side_effect = side_effect

            repo = SnapshotRepository(
                r2_client=r2_client,
                sync_service=mock_sync_service,
                allow_network=True,
            )

            result = repo.ensure_fx_snapshot(date(2026, 1, 10), 'daily')

            assert result is not None
            # Verify R2 was populated
            r2_data = r2_client.get_snapshot('fx', 'daily', date(2026, 1, 10))
            assert r2_data is not None
            assert r2_data['source'] == 'upstream'


class TestFactoryFunction:
    """Test get_snapshot_repository factory."""

    def test_factory_creates_repository(self, monkeypatch):
        """Factory creates SnapshotRepository with correct defaults."""
        # Disable R2
        monkeypatch.setenv('R2_ENABLED', '0')

        repo = get_snapshot_repository(allow_network=False)

        assert isinstance(repo, SnapshotRepository)
        assert repo._r2 is None  # R2 disabled
        assert repo._sync_service is None
        assert repo._allow_network is False

    def test_factory_accepts_sync_service(self, monkeypatch, mock_sync_service):
        """Factory accepts custom sync_service."""
        monkeypatch.setenv('R2_ENABLED', '0')

        repo = get_snapshot_repository(
            allow_network=True,
            sync_service=mock_sync_service,
        )

        assert repo._sync_service is mock_sync_service
        assert repo._allow_network is True
