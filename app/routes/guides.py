"""Guides content hub routes."""

import json

from flask import Blueprint, Response, abort, render_template, request

from app.content.guides import GUIDES
from app.services.seo import (
    build_article_schema,
    build_breadcrumb_schema,
    build_faq_schema,
)

guides_bp = Blueprint('guides', __name__)

CORE_LASTMOD = "2026-01-15"


def _absolute_url(path: str) -> str:
    root = request.url_root.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{root}{path}"


@guides_bp.route('/guides')
def index():
    """Render the guides index page."""
    guides = list(GUIDES.values())
    canonical_url = _absolute_url("/guides")
    return render_template(
        'guides_index.html',
        guides=guides,
        canonical_url=canonical_url,
        meta_title="Zakat Guides - Practical Calculation Help",
        meta_description=(
            "Explore practical Zakat guides on gold, cash, crypto, stocks, and more. "
            "Clear steps, FAQs, and links to the calculator."
        ),
    )


def guide_page(slug: str):
    """Render an individual guide page."""
    guide = GUIDES.get(slug)
    if not guide:
        abort(404)

    canonical_url = _absolute_url(f"/{slug}")
    faq_schema_json = json.dumps(build_faq_schema(guide), ensure_ascii=False)
    breadcrumb_schema_json = json.dumps(
        build_breadcrumb_schema(guide, request.url_root), ensure_ascii=False
    )
    article_schema_json = json.dumps(
        build_article_schema(guide, canonical_url), ensure_ascii=False
    )
    related_guides = [
        GUIDES[related_slug]
        for related_slug in guide.get("related", [])
        if related_slug in GUIDES
    ]

    return render_template(
        'guide.html',
        guide=guide,
        canonical_url=canonical_url,
        faq_schema_json=faq_schema_json,
        breadcrumb_schema_json=breadcrumb_schema_json,
        article_schema_json=article_schema_json,
        related_guides=related_guides,
    )


@guides_bp.route('/sitemap.xml')
def sitemap():
    """Return XML sitemap with core pages and guide URLs."""
    items = [
        ("/", CORE_LASTMOD),
        ("/about-zakat", CORE_LASTMOD),
        ("/faq", CORE_LASTMOD),
        ("/contact", CORE_LASTMOD),
        ("/guides", CORE_LASTMOD),
        ("/charities", "2026-02-20"),
    ]
    for guide in GUIDES.values():
        items.append((f"/{guide['slug']}", guide["last_modified"]))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in items:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{_absolute_url(path)}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")


@guides_bp.route('/robots.txt')
def robots():
    """Return robots.txt allowing all crawlers and pointing to the sitemap."""
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {_absolute_url('/sitemap.xml')}",
            "",
        ]
    )
    return Response(content, mimetype="text/plain")


for slug in GUIDES.keys():
    guides_bp.add_url_rule(
        f"/{slug}",
        endpoint=f"guide_{slug}",
        view_func=guide_page,
        defaults={"slug": slug},
    )
