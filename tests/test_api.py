"""Tests for API pricing endpoint."""
import pytest

from app.services import cache


@pytest.fixture
def temp_data_dir(monkeypatch, tmp_path):
    """Use temporary directory for cache tests."""
    monkeypatch.setattr(cache, 'DATA_DIR', str(tmp_path))
    return tmp_path


def test_pricing_returns_200(client, temp_data_dir):
    """GET /api/v1/pricing/legacy should return status 200."""
    response = client.get('/api/v1/pricing/legacy')
    assert response.status_code == 200


def test_pricing_returns_required_keys(client, temp_data_dir):
    """GET /api/v1/pricing/legacy should return all required keys."""
    response = client.get('/api/v1/pricing/legacy')
    data = response.get_json()

    required_keys = ['base_currency', 'fx_rates', 'metals', 'zakat_rate', 'as_of', 'cache_status']
    for key in required_keys:
        assert key in data, f"Missing required key: {key}"


def test_pricing_zakat_rate_is_correct(client, temp_data_dir):
    """GET /api/v1/pricing/legacy should return zakat_rate of 0.025 (2.5%)."""
    response = client.get('/api/v1/pricing/legacy')
    data = response.get_json()
    assert data['zakat_rate'] == 0.025


def test_pricing_gold_has_nisab_info(client, temp_data_dir):
    """GET /api/v1/pricing/legacy gold data should include nisab info (85 grams)."""
    response = client.get('/api/v1/pricing/legacy')
    data = response.get_json()

    assert 'nisab_grams' in data['metals']['gold']
    assert data['metals']['gold']['nisab_grams'] == 85


def test_pricing_silver_has_nisab_info(client, temp_data_dir):
    """GET /api/v1/pricing/legacy silver data should include nisab info (595 grams)."""
    response = client.get('/api/v1/pricing/legacy')
    data = response.get_json()

    assert 'nisab_grams' in data['metals']['silver']
    assert data['metals']['silver']['nisab_grams'] == 595


def test_pricing_refresh_returns_200(client, temp_data_dir):
    """POST /api/v1/pricing/refresh should return status 200."""
    response = client.post('/api/v1/pricing/refresh')
    assert response.status_code == 200


def test_pricing_refresh_returns_refreshed_status(client, temp_data_dir):
    """POST /api/v1/pricing/refresh should return cache_status of refreshed."""
    # First populate cache
    client.get('/api/v1/pricing/legacy')
    # Then refresh
    response = client.post('/api/v1/pricing/refresh')
    data = response.get_json()
    assert data['cache_status'] == 'refreshed'


def test_pricing_cache_hit_on_second_call(client, temp_data_dir):
    """Second GET /api/v1/pricing/legacy should return cache hit."""
    client.get('/api/v1/pricing/legacy')  # First call
    response = client.get('/api/v1/pricing/legacy')  # Second call
    data = response.get_json()
    assert data['cache_status'] == 'hit'
