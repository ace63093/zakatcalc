"""Tests for pricing sync endpoints."""
import pytest
from unittest.mock import patch, MagicMock

from app.db import get_db
from tests.conftest import TEST_ADMIN_SECRET

ADMIN_HEADERS = {'X-Admin-Secret': TEST_ADMIN_SECRET}


class TestSyncStatusEndpoint:
    """Tests for GET /api/v1/pricing/sync-status."""

    def test_returns_sync_status(self, db_client):
        """Sync status endpoint returns expected structure."""
        response = db_client.get('/api/v1/pricing/sync-status')
        assert response.status_code == 200

        data = response.get_json()
        assert 'sync_enabled' in data
        assert 'auto_sync_enabled' in data
        assert 'last_changes_reported' in data
        assert 'providers' in data
        assert 'data_coverage' in data
        assert 'daemon' in data  # Can be None if daemon hasn't run yet

    def test_providers_structure(self, db_client):
        """Provider status has correct structure."""
        response = db_client.get('/api/v1/pricing/sync-status')
        data = response.get_json()

        providers = data['providers']
        assert 'fx' in providers
        assert 'metals' in providers
        assert 'crypto' in providers

        for provider_type in ['fx', 'metals', 'crypto']:
            assert 'provider' in providers[provider_type]
            assert 'requires_key' in providers[provider_type]
            assert 'configured' in providers[provider_type]

    def test_data_coverage_structure(self, db_client):
        """Data coverage has correct structure."""
        response = db_client.get('/api/v1/pricing/sync-status')
        data = response.get_json()

        coverage = data['data_coverage']
        assert 'fx' in coverage
        assert 'metals' in coverage
        assert 'crypto' in coverage

    def test_r2_enabled_field(self, db_client):
        """Sync status includes r2_enabled field."""
        response = db_client.get('/api/v1/pricing/sync-status')
        data = response.get_json()

        assert 'r2_enabled' in data
        assert isinstance(data['r2_enabled'], bool)

    def test_last_changes_reported_defaults_to_zero(self, db_client):
        """Sync status returns zero when daemon state is missing."""
        response = db_client.get('/api/v1/pricing/sync-status')
        data = response.get_json()

        assert 'last_changes_reported' in data
        assert isinstance(data['last_changes_reported'], int)
        assert data['last_changes_reported'] >= 0

    @patch('app.routes.api.get_sync_service')
    def test_last_changes_reported_uses_daemon_snapshots_synced(self, mock_get_sync, db_client):
        """Sync status should expose daemon snapshots_synced as last_changes_reported."""
        mock_service = MagicMock()
        mock_service.get_data_coverage.return_value = {'fx': {}, 'metals': {}, 'crypto': {}}
        mock_service.get_daemon_state.return_value = {
            'last_sync_at': '2026-02-07T22:03:24+00:00',
            'last_sync_result': 'success',
            'last_error': None,
            'next_sync_at': '2026-02-07T23:03:24+00:00',
            'snapshots_synced': 7,
            'updated_at': '2026-02-07T22:03:24+00:00',
        }
        mock_get_sync.return_value = mock_service

        response = db_client.get('/api/v1/pricing/sync-status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['last_changes_reported'] == 7


class TestSyncDateEndpoint:
    """Tests for POST /api/v1/pricing/sync-date."""

    @patch('app.routes.api.is_sync_enabled', return_value=False)
    def test_sync_disabled_returns_403(self, mock_enabled, db_client):
        """Sync-date returns 403 when sync is disabled."""
        response = db_client.post('/api/v1/pricing/sync-date',
                                  json={'date': '2026-01-05'}, headers=ADMIN_HEADERS)
        assert response.status_code == 403

        data = response.get_json()
        assert 'error' in data
        assert 'Network sync disabled' in data['error']

    @patch('app.routes.api.is_sync_enabled', return_value=True)
    def test_missing_date_returns_400(self, mock_enabled, db_client):
        """Sync-date requires date parameter."""
        response = db_client.post('/api/v1/pricing/sync-date', json={}, headers=ADMIN_HEADERS)
        assert response.status_code == 400

        data = response.get_json()
        assert 'date is required' in data['error']

    @patch('app.routes.api.is_sync_enabled', return_value=True)
    def test_invalid_date_format(self, mock_enabled, db_client):
        """Invalid date format returns 400."""
        response = db_client.post('/api/v1/pricing/sync-date',
                                  json={'date': 'not-a-date'}, headers=ADMIN_HEADERS)
        assert response.status_code == 400

        data = response.get_json()
        assert 'Invalid date format' in data['error']

    @patch('app.routes.api.is_sync_enabled', return_value=True)
    @patch('app.routes.api.get_sync_service')
    def test_successful_sync(self, mock_get_sync, mock_enabled, db_client):
        """Successful sync returns results."""
        mock_service = MagicMock()
        mock_service.sync_date.return_value = {
            'success': True,
            'date': '2026-01-05',
            'results': {
                'fx': {'status': 'success', 'records': 10},
                'metals': {'status': 'success', 'records': 4},
                'crypto': {'status': 'success', 'records': 100},
            },
            'synced_at': '2026-01-05T12:00:00Z'
        }
        mock_get_sync.return_value = mock_service

        response = db_client.post('/api/v1/pricing/sync-date',
                                  json={'date': '2026-01-05'}, headers=ADMIN_HEADERS)
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'results' in data


class TestSyncRangeEndpoint:
    """Tests for POST /api/v1/pricing/sync."""

    @patch('app.routes.api.is_sync_enabled', return_value=False)
    def test_sync_disabled_returns_403(self, mock_enabled, db_client):
        """Sync returns 403 when sync is disabled."""
        response = db_client.post('/api/v1/pricing/sync',
                                  json={'start_date': '2026-01-01', 'end_date': '2026-01-05'},
                                  headers=ADMIN_HEADERS)
        assert response.status_code == 403

    @patch('app.routes.api.is_sync_enabled', return_value=True)
    def test_requires_start_and_end_date(self, mock_enabled, db_client):
        """Sync requires both start_date and end_date."""
        response = db_client.post('/api/v1/pricing/sync',
                                  json={'start_date': '2026-01-01'}, headers=ADMIN_HEADERS)
        assert response.status_code == 400

        response = db_client.post('/api/v1/pricing/sync',
                                  json={'end_date': '2026-01-05'}, headers=ADMIN_HEADERS)
        assert response.status_code == 400

    @patch('app.routes.api.is_sync_enabled', return_value=True)
    def test_start_after_end_returns_400(self, mock_enabled, db_client):
        """Start date after end date returns 400."""
        response = db_client.post('/api/v1/pricing/sync',
                                  json={'start_date': '2026-01-10', 'end_date': '2026-01-05'},
                                  headers=ADMIN_HEADERS)
        assert response.status_code == 400

        data = response.get_json()
        assert 'start_date must be before' in data['error']

    @patch('app.routes.api.is_sync_enabled', return_value=True)
    @patch('app.routes.api.get_sync_service')
    def test_successful_range_sync(self, mock_get_sync, mock_enabled, db_client):
        """Successful range sync returns results."""
        mock_service = MagicMock()
        mock_service.sync_range.return_value = {
            'success': True,
            'sync_results': {
                'fx': {'status': 'success', 'dates_requested': 5, 'dates_synced': 5},
                'metals': {'status': 'success', 'dates_requested': 5, 'dates_synced': 5},
                'crypto': {'status': 'success', 'dates_requested': 5, 'dates_synced': 5},
            },
            'synced_at': '2026-01-05T12:00:00Z'
        }
        mock_get_sync.return_value = mock_service

        response = db_client.post('/api/v1/pricing/sync',
                                  json={'start_date': '2026-01-01', 'end_date': '2026-01-05'},
                                  headers=ADMIN_HEADERS)
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True


class TestPricingEndpointAutoSync:
    """Tests for auto_sync in /api/v1/pricing response."""

    def test_pricing_includes_auto_sync(self, db_client):
        """Pricing endpoint includes auto_sync."""
        response = db_client.get('/api/v1/pricing?date=2025-01-01')
        assert response.status_code == 200

        data = response.get_json()
        assert 'auto_sync' in data
        assert 'cadence' in data

    def test_auto_sync_structure(self, db_client):
        """Auto sync has correct structure."""
        response = db_client.get('/api/v1/pricing?date=2025-01-01')
        data = response.get_json()

        auto_sync = data['auto_sync']
        assert 'enabled' in auto_sync
        assert 'jit_synced' in auto_sync

    def test_sync_enabled_by_default(self, db_client):
        """Sync is enabled by default (auto-sync mode)."""
        response = db_client.get('/api/v1/pricing?date=2025-01-01')
        data = response.get_json()

        assert data['auto_sync']['enabled'] is True


class TestVisitorSyncNowEndpoint:
    """Tests for POST /api/v1/visitors/sync-now."""

    @patch('app.routes.api.is_visitor_logging_enabled', return_value=False)
    def test_visitor_logging_disabled_returns_403(self, mock_enabled, db_client):
        response = db_client.post('/api/v1/visitors/sync-now', headers=ADMIN_HEADERS)
        assert response.status_code == 403

        data = response.get_json()
        assert 'error' in data
        assert 'Visitor logging disabled' in data['error']

    @patch('app.routes.api.is_visitor_logging_enabled', return_value=True)
    @patch('app.routes.api.get_r2_client', return_value=None)
    def test_r2_unavailable_returns_503(self, mock_get_r2, mock_enabled, db_client):
        response = db_client.post('/api/v1/visitors/sync-now', headers=ADMIN_HEADERS)
        assert response.status_code == 503

        data = response.get_json()
        assert 'error' in data
        assert 'R2 unavailable' in data['error']

    @patch('app.routes.api.is_visitor_logging_enabled', return_value=True)
    @patch('app.routes.api.backfill_visitor_geolocation', return_value={'status': 'ok', 'updated': 0})
    @patch('app.routes.api.backup_visitors_to_r2')
    @patch('app.routes.api.get_r2_client')
    def test_sync_now_reports_com_and_ca_rollups(
        self, mock_get_r2, mock_backup, mock_geo_backfill, mock_enabled, db_client
    ):
        mock_get_r2.return_value = MagicMock()

        with db_client.application.app_context():
            db = get_db()
            db.executemany(
                'INSERT INTO visitors (ip_hash, user_agent) VALUES (?, ?)',
                [
                    ('ip-1', 'ua'),
                    ('ip-2', 'ua'),
                    ('ip-3', 'ua'),
                ],
            )
            db.executemany(
                'INSERT INTO visitor_domains (ip_hash, host, visit_count) VALUES (?, ?, ?)',
                [
                    ('ip-1', 'whatismyzakat.com', 2),
                    ('ip-2', 'www.whatismyzakat.com', 1),
                    ('ip-1', 'whatismyzakat.ca', 3),
                    ('ip-3', 'www.whatismyzakat.ca', 1),
                    ('ip-3', 'example.net', 5),
                ],
            )
            db.commit()

        response = db_client.post('/api/v1/visitors/sync-now', headers=ADMIN_HEADERS)
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert data['totals']['unique_ips'] == 3
        assert data['totals']['domain_rows'] == 5
        assert data['domains']['whatismyzakat.com']['unique_ips'] == 2
        assert data['domains']['whatismyzakat.com']['visits'] == 3
        assert data['domains']['whatismyzakat.ca']['unique_ips'] == 2
        assert data['domains']['whatismyzakat.ca']['visits'] == 4
        assert data['geo_backfill']['status'] == 'ok'
        mock_backup.assert_called_once()
        mock_geo_backfill.assert_called_once()
