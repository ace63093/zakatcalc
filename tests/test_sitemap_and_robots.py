"""Tests for sitemap.xml and robots.txt."""

from app.content.guides import GUIDES


def test_sitemap_contains_guide_urls(client):
    """Sitemap should list every guide URL."""
    response = client.get('/sitemap.xml')
    assert response.status_code == 200

    xml = response.data.decode('utf-8')
    assert '/guides</loc>' in xml
    assert '/about-zakat</loc>' in xml
    assert '/faq</loc>' in xml
    assert '/contact</loc>' in xml

    for slug in GUIDES.keys():
        assert f'/{slug}</loc>' in xml


def test_robots_contains_sitemap(client):
    """Robots should allow all and link to sitemap."""
    response = client.get('/robots.txt')
    assert response.status_code == 200

    text = response.data.decode('utf-8')
    assert 'User-agent: *' in text
    assert 'Sitemap:' in text
    assert '/sitemap.xml' in text
