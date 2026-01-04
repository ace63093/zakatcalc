"""Tests for health check endpoint."""


def test_healthz_returns_200(client):
    """GET /healthz should return status 200."""
    response = client.get('/healthz')
    assert response.status_code == 200


def test_healthz_returns_json_status_ok(client):
    """GET /healthz should return JSON with status ok."""
    response = client.get('/healthz')
    data = response.get_json()
    assert data == {'status': 'ok'}
