"""Tests for guides pages."""

import pytest

from app.content.guides import GUIDES


def test_guides_index_returns_200(client):
    """GET /guides should return status 200."""
    response = client.get('/guides')
    assert response.status_code == 200


def test_guides_index_contains_all_guide_links(client):
    """GET /guides should contain links to each guide slug."""
    response = client.get('/guides')
    assert response.status_code == 200

    html = response.data.decode('utf-8')
    for slug in GUIDES.keys():
        assert f'href="/{slug}"' in html


@pytest.mark.parametrize("slug", GUIDES.keys())
def test_guide_pages_have_seo_elements(client, slug):
    """Each guide page should include SEO essentials and a calculator CTA."""
    response = client.get(f'/{slug}')
    assert response.status_code == 200

    html = response.data.decode('utf-8')
    assert 'name="description"' in html
    assert 'rel="canonical"' in html
    assert 'application/ld+json' in html
    assert 'data-cta="calculator" href="/"' in html


def test_unknown_slug_returns_404(client):
    """Unknown guide slugs should return 404, not 500."""
    response = client.get('/this-is-not-a-valid-guide-slug')
    assert response.status_code == 404
