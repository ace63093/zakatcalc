"""Tests for API pricing endpoint."""


def test_pricing_returns_200(client):
    """GET /api/v1/pricing should return status 200."""
    response = client.get('/api/v1/pricing')
    assert response.status_code == 200


def test_pricing_returns_required_keys(client):
    """GET /api/v1/pricing should return all required keys."""
    response = client.get('/api/v1/pricing')
    data = response.get_json()

    required_keys = ['gold', 'silver', 'currency', 'zakat_rate', 'last_updated']
    for key in required_keys:
        assert key in data, f"Missing required key: {key}"


def test_pricing_zakat_rate_is_correct(client):
    """GET /api/v1/pricing should return zakat_rate of 0.025 (2.5%)."""
    response = client.get('/api/v1/pricing')
    data = response.get_json()
    assert data['zakat_rate'] == 0.025


def test_pricing_gold_has_nisab_info(client):
    """GET /api/v1/pricing gold data should include nisab info (85 grams)."""
    response = client.get('/api/v1/pricing')
    data = response.get_json()

    assert 'nisab_grams' in data['gold']
    assert data['gold']['nisab_grams'] == 85


def test_pricing_silver_has_nisab_info(client):
    """GET /api/v1/pricing silver data should include nisab info (595 grams)."""
    response = client.get('/api/v1/pricing')
    data = response.get_json()

    assert 'nisab_grams' in data['silver']
    assert data['silver']['nisab_grams'] == 595
