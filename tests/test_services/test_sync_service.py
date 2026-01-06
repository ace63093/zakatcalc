"""Tests for SyncService R2 integration."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.sync import SyncService
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


class TestSyncServiceR2Integration:
    """Test R2 mirroring in SyncService."""

    def test_sync_service_accepts_r2_client(self, r2_client):
        """SyncService can be initialized with explicit R2 client."""
        svc = SyncService(r2_client=r2_client)
        assert svc._r2 is r2_client

    def test_sync_service_r2_none_when_disabled(self, monkeypatch):
        """SyncService has None R2 when R2 is disabled."""
        monkeypatch.setenv('R2_ENABLED', '0')
        svc = SyncService()
        assert svc._r2 is None

    @patch('app.services.sync.get_fx_provider')
    @patch('app.services.sync.get_metal_provider')
    @patch('app.services.sync.get_crypto_provider')
    def test_mirror_to_r2_called_after_sync(
        self,
        mock_crypto_provider,
        mock_metal_provider,
        mock_fx_provider,
        r2_client,
        fake_r2,
        db_app,
    ):
        """R2 mirroring is called after successful sync."""
        with db_app.app_context():
            # Setup mock providers
            fx_provider = MagicMock()
            fx_provider.name = 'test-fx'
            fx_rate = MagicMock()
            fx_rate.currency = 'EUR'
            fx_rate.rate_to_usd = 0.91
            fx_rate.source = 'test'
            fx_provider.get_rates.return_value = [fx_rate]
            mock_fx_provider.return_value = fx_provider

            metal_provider = MagicMock()
            metal_provider.name = 'test-metal'
            metal_price = MagicMock()
            metal_price.metal = 'gold'
            metal_price.price_per_gram_usd = 85.0
            metal_price.source = 'test'
            metal_provider.get_prices.return_value = [metal_price]
            mock_metal_provider.return_value = metal_provider

            crypto_provider = MagicMock()
            crypto_provider.name = 'test-crypto'
            crypto_price = MagicMock()
            crypto_price.symbol = 'BTC'
            crypto_price.name = 'Bitcoin'
            crypto_price.price_usd = 100000.0
            crypto_price.rank = 1
            crypto_price.source = 'test'
            crypto_provider.get_prices.return_value = [crypto_price]
            mock_crypto_provider.return_value = crypto_provider

            # Create service with R2 client
            svc = SyncService(r2_client=r2_client)

            # Perform sync
            result = svc.sync_date(date(2026, 1, 15), snapshot_type='daily')

            # Verify sync succeeded
            assert result['success'] is True

            # Verify R2 has the mirrored data
            fx_snapshot = r2_client.get_snapshot('fx', 'daily', date(2026, 1, 15))
            assert fx_snapshot is not None
            assert fx_snapshot['data']['EUR'] == 0.91

            metals_snapshot = r2_client.get_snapshot('metals', 'daily', date(2026, 1, 15))
            assert metals_snapshot is not None
            assert metals_snapshot['data']['gold'] == 85.0

            crypto_snapshot = r2_client.get_snapshot('crypto', 'daily', date(2026, 1, 15))
            assert crypto_snapshot is not None
            assert crypto_snapshot['data']['BTC']['price'] == 100000.0

    @patch('app.services.sync.get_fx_provider')
    @patch('app.services.sync.get_metal_provider')
    @patch('app.services.sync.get_crypto_provider')
    def test_r2_failure_does_not_break_sync(
        self,
        mock_crypto_provider,
        mock_metal_provider,
        mock_fx_provider,
        db_app,
    ):
        """R2 errors are logged but don't fail the sync."""
        with db_app.app_context():
            # Setup mock providers
            fx_provider = MagicMock()
            fx_provider.name = 'test-fx'
            fx_rate = MagicMock()
            fx_rate.currency = 'EUR'
            fx_rate.rate_to_usd = 0.91
            fx_rate.source = 'test'
            fx_provider.get_rates.return_value = [fx_rate]
            mock_fx_provider.return_value = fx_provider

            metal_provider = MagicMock()
            metal_provider.name = 'test-metal'
            metal_provider.get_prices.return_value = []
            mock_metal_provider.return_value = metal_provider

            crypto_provider = MagicMock()
            crypto_provider.name = 'test-crypto'
            crypto_provider.get_prices.return_value = []
            mock_crypto_provider.return_value = crypto_provider

            # Create failing R2 client
            failing_r2 = MagicMock()
            failing_r2.put_snapshot.side_effect = Exception("R2 connection failed")

            svc = SyncService(r2_client=failing_r2)

            # Sync should still succeed even though R2 failed
            result = svc.sync_date(date(2026, 1, 16), types=['fx'], snapshot_type='daily')

            # FX sync succeeded
            assert result['results']['fx']['status'] == 'success'

    def test_no_r2_mirror_when_disabled(self, monkeypatch, db_app):
        """No R2 mirroring when R2 is disabled."""
        with db_app.app_context():
            monkeypatch.setenv('R2_ENABLED', '0')

            svc = SyncService()

            # _mirror_to_r2 should be a no-op when R2 is None
            # This shouldn't raise even with data
            svc._mirror_to_r2(
                date(2026, 1, 17),
                'daily',
                {'EUR': 0.91},
                {'gold': 85.0},
                {'BTC': {'name': 'Bitcoin', 'price': 100000.0, 'rank': 1}},
            )
