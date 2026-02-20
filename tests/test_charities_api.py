"""Tests for GET /api/v1/charities endpoint."""
from app.content.charities import CHARITIES


def test_charities_api_returns_200(client):
    response = client.get('/api/v1/charities')
    assert response.status_code == 200

def test_charities_api_returns_all(client):
    response = client.get('/api/v1/charities')
    data = response.get_json()
    assert data['count'] == len(CHARITIES)

def test_charities_api_filter_ca(client):
    response = client.get('/api/v1/charities?country=CA')
    data = response.get_json()
    assert data['count'] > 0
    for c in data['charities']:
        assert c['country'] == 'CA'

def test_charities_api_filter_us(client):
    response = client.get('/api/v1/charities?country=US')
    data = response.get_json()
    assert data['count'] > 0
    for c in data['charities']:
        assert c['country'] == 'US'

def test_charities_api_case_insensitive(client):
    r1 = client.get('/api/v1/charities?country=ca')
    r2 = client.get('/api/v1/charities?country=CA')
    assert r1.get_json()['count'] == r2.get_json()['count']

def test_charities_api_unknown_country_empty(client):
    response = client.get('/api/v1/charities?country=XX')
    data = response.get_json()
    assert response.status_code == 200
    assert data['count'] == 0

def test_charities_api_required_fields(client):
    response = client.get('/api/v1/charities')
    data = response.get_json()
    required = {'id', 'name', 'country', 'description', 'registration_label', 'website', 'donate_url', 'tags', 'featured'}
    for charity in data['charities']:
        for field in required:
            assert field in charity
