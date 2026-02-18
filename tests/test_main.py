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


def test_calculator_includes_favicon_links(client):
    """GET / should include favicon and manifest links in head."""
    response = client.get('/')
    assert b'favicon-16x16.png' in response.data
    assert b'favicon-32x32.png' in response.data
    assert b'apple-touch-icon.png' in response.data
    assert b'site.webmanifest' in response.data


def test_no_ad_network_snippets_on_all_main_pages(client):
    """Main UI pages should not include disabled ad network snippets."""
    paths = (
        '/',
        '/about-zakat',
        '/faq',
        '/contact',
        '/privacy-policy',
        '/methodology',
        '/cad-to-bdt',
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert b'<meta name="monetag"' not in response.data
        assert b'infolinks_main.js' not in response.data
        assert b'ezojs.com/ezoic/sa.min.js' not in response.data


def test_favicon_route_returns_icon(client):
    """GET /favicon.ico should return icon content."""
    response = client.get('/favicon.ico')
    assert response.status_code == 200
    assert response.content_type in ('image/x-icon', 'image/vnd.microsoft.icon')


def test_calculator_does_not_render_in_page_logo(client):
    """GET / should not render the in-page header logo block."""
    response = client.get('/')
    assert b'class="site-brand"' not in response.data


def test_calculator_crypto_section_scoped_to_advanced_mode_when_enabled(client):
    """When advanced mode toggle exists, crypto section should live inside advanced container."""
    response = client.get('/')
    html = response.data.decode('utf-8')

    if 'id="advancedModeToggle"' not in html:
        assert 'id="cryptoItems"' in html
        return

    advanced_index = html.find('id="advancedAssetsContainer"')
    crypto_index = html.find('id="cryptoItems"')

    assert advanced_index != -1
    assert crypto_index != -1
    assert crypto_index > advanced_index


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


def test_privacy_policy_returns_200(client):
    """GET /privacy-policy should return status 200."""
    response = client.get('/privacy-policy')
    assert response.status_code == 200


def test_privacy_policy_contains_heading(client):
    """GET /privacy-policy should contain Privacy Policy heading."""
    response = client.get('/privacy-policy')
    assert b'Privacy Policy' in response.data


def test_methodology_returns_200(client):
    """GET /methodology should return status 200."""
    response = client.get('/methodology')
    assert response.status_code == 200


def test_methodology_contains_heading(client):
    """GET /methodology should contain Methodology heading."""
    response = client.get('/methodology')
    assert b'Calculation Methodology' in response.data


def test_methodology_contains_jsonld(client):
    """GET /methodology should contain JSON-LD structured data."""
    response = client.get('/methodology')
    assert b'application/ld+json' in response.data
    assert b'schema.org' in response.data


def test_cad_to_bdt_returns_200(client):
    """GET /cad-to-bdt should return status 200."""
    response = client.get('/cad-to-bdt')
    assert response.status_code == 200


def test_cad_to_bdt_contains_heading(client):
    """GET /cad-to-bdt should contain CAD to BDT heading."""
    response = client.get('/cad-to-bdt')
    assert b'CAD to BDT' in response.data
