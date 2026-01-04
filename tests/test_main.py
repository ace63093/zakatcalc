"""Tests for main UI routes."""


def test_calculator_returns_200(client):
    """GET / should return status 200."""
    response = client.get('/')
    assert response.status_code == 200


def test_calculator_returns_html(client):
    """GET / should return HTML content."""
    response = client.get('/')
    assert response.content_type.startswith('text/html')


def test_calculator_contains_zakat_title(client):
    """GET / should contain Zakat Calculator in the page."""
    response = client.get('/')
    assert b'Zakat Calculator' in response.data
