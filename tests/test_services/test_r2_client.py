"""Tests for R2 client - no network calls."""
import gzip
import json
from datetime import date

import pytest

from app.services.r2_client import R2Client
from tests.fakes.fake_r2 import FakeR2


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


class TestR2ClientPutGet:
    """Test put/get snapshot operations."""

    def test_put_snapshot_creates_gzip_json(self, r2_client, fake_r2):
        """Verify put creates gzip-compressed JSON."""
        payload = {
            'source': 'test',
            'created_at': '2026-01-06T12:00:00Z',
            'data': {'CAD': 1.38, 'EUR': 0.91},
        }

        key = r2_client.put_snapshot('fx', 'daily', date(2026, 1, 6), payload)

        assert key == 'pricing/fx/daily/2026-01-06.json.gz'

        # Verify stored object is gzip
        stored = fake_r2._objects['test-bucket/pricing/fx/daily/2026-01-06.json.gz']
        decompressed = gzip.decompress(stored['Body'])
        data = json.loads(decompressed)

        assert data['type'] == 'fx'
        assert data['cadence'] == 'daily'
        assert data['effective_date'] == '2026-01-06'
        assert data['base'] == 'USD'
        assert data['data'] == {'CAD': 1.38, 'EUR': 0.91}

    def test_get_snapshot_decompresses_correctly(self, r2_client, fake_r2):
        """Verify get decompresses and returns JSON."""
        # Put first
        payload = {
            'source': 'test',
            'data': {'gold': 85.0, 'silver': 1.05},
        }
        r2_client.put_snapshot('metals', 'weekly', date(2025, 12, 30), payload)

        # Get back
        result = r2_client.get_snapshot('metals', 'weekly', date(2025, 12, 30))

        assert result is not None
        assert result['type'] == 'metals'
        assert result['cadence'] == 'weekly'
        assert result['data'] == {'gold': 85.0, 'silver': 1.05}

    def test_get_snapshot_returns_none_if_missing(self, r2_client):
        """Verify get returns None for missing snapshot."""
        result = r2_client.get_snapshot('fx', 'daily', date(2020, 1, 1))
        assert result is None


class TestR2ClientHasSnapshot:
    """Test has_snapshot (HEAD) operations."""

    def test_has_snapshot_returns_true_if_exists(self, r2_client):
        """Verify HEAD returns true for existing object."""
        r2_client.put_snapshot('crypto', 'monthly', date(2025, 1, 1), {'data': {}})

        assert r2_client.has_snapshot('crypto', 'monthly', date(2025, 1, 1)) is True

    def test_has_snapshot_returns_false_if_missing(self, r2_client):
        """Verify HEAD returns false for missing object."""
        assert r2_client.has_snapshot('fx', 'daily', date(1999, 1, 1)) is False


class TestR2ClientListSnapshots:
    """Test list_snapshots operations."""

    def test_list_snapshots_with_filter(self, r2_client):
        """Verify list with type and cadence filter."""
        r2_client.put_snapshot('fx', 'daily', date(2026, 1, 5), {'data': {}})
        r2_client.put_snapshot('fx', 'daily', date(2026, 1, 6), {'data': {}})
        r2_client.put_snapshot('fx', 'weekly', date(2025, 12, 30), {'data': {}})
        r2_client.put_snapshot('metals', 'daily', date(2026, 1, 6), {'data': {}})

        fx_daily = r2_client.list_snapshots(data_type='fx', cadence='daily')

        assert len(fx_daily) == 2
        assert 'pricing/fx/daily/2026-01-05.json.gz' in fx_daily
        assert 'pricing/fx/daily/2026-01-06.json.gz' in fx_daily


class TestR2ClientDecompressionFallback:
    """Test decompression fallback for already-decompressed content."""

    def test_get_snapshot_handles_already_decompressed(self, r2_client, fake_r2):
        """Verify get handles content already decompressed by client.

        Some S3/R2 clients transparently decompress content when
        Content-Encoding is gzip. The R2Client should handle both cases.
        """
        # Manually store uncompressed JSON (simulating transparent decompression)
        payload = {
            'version': '1.0',
            'type': 'fx',
            'cadence': 'daily',
            'effective_date': '2026-01-10',
            'base': 'USD',
            'data': {'CAD': 1.40, 'EUR': 0.95},
        }
        uncompressed_json = json.dumps(payload).encode('utf-8')

        # Store directly in fake without gzip compression
        fake_r2._objects['test-bucket/pricing/fx/daily/2026-01-10.json.gz'] = {
            'Body': uncompressed_json,  # Already decompressed
            'ContentType': 'application/json',
            'ContentEncoding': 'gzip',  # Header still says gzip
        }

        # get_snapshot should handle this gracefully
        result = r2_client.get_snapshot('fx', 'daily', date(2026, 1, 10))

        assert result is not None
        assert result['type'] == 'fx'
        assert result['data'] == {'CAD': 1.40, 'EUR': 0.95}


class TestR2ClientKeyNaming:
    """Test key naming convention."""

    def test_key_without_prefix(self, r2_client):
        """Verify key format without prefix."""
        key = r2_client._make_key('fx', 'daily', date(2026, 1, 6))
        assert key == 'pricing/fx/daily/2026-01-06.json.gz'

    def test_key_with_prefix(self, fake_r2, monkeypatch):
        """Verify key format with prefix."""
        monkeypatch.setenv('R2_ENABLED', '1')
        monkeypatch.setenv('R2_BUCKET', 'test-bucket')
        monkeypatch.setenv('R2_ENDPOINT_URL', 'https://fake.r2.dev')
        monkeypatch.setenv('R2_ACCESS_KEY_ID', 'fake-key')
        monkeypatch.setenv('R2_SECRET_ACCESS_KEY', 'fake-secret')
        monkeypatch.setenv('R2_PREFIX', 'zakat-app/')

        client = R2Client(s3_client=fake_r2)
        key = client._make_key('metals', 'monthly', date(2025, 1, 1))

        assert key == 'zakat-app/pricing/metals/monthly/2025-01-01.json.gz'
