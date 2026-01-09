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


def test_about_zakat_returns_200(client):
    """GET /about-zakat should return status 200."""
    response = client.get('/about-zakat')
    assert response.status_code == 200


def test_about_zakat_contains_heading(client):
    """GET /about-zakat should contain About Zakat heading."""
    response = client.get('/about-zakat')
    assert b'About Zakat' in response.data


def test_faq_returns_200(client):
    """GET /faq should return status 200."""
    response = client.get('/faq')
    assert response.status_code == 200


def test_faq_contains_heading(client):
    """GET /faq should contain Zakat FAQ heading."""
    response = client.get('/faq')
    assert b'Zakat FAQ' in response.data


def test_contact_returns_200(client):
    """GET /contact should return status 200."""
    response = client.get('/contact')
    assert response.status_code == 200


def test_contact_contains_heading(client):
    """GET /contact should contain Contact Us heading."""
    response = client.get('/contact')
    assert b'Contact Us' in response.data
