"""Helpers for generating SEO JSON-LD schemas."""

from flask import url_for

SITE_NAME = "Zakat Calculator"


def build_faq_schema(guide: dict) -> dict:
    """Build FAQPage schema for a guide."""
    entities = []
    for faq in guide.get("faqs", []):
        entities.append(
            {
                "@type": "Question",
                "name": faq["q"],
                "acceptedAnswer": {"@type": "Answer", "text": faq["a"]},
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }


def _absolute_url(url_root: str, path: str) -> str:
    root = url_root.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{root}{path}"


def build_breadcrumb_schema(guide: dict, url_root: str) -> dict:
    """Build BreadcrumbList schema for a guide."""
    items = []
    for position, crumb in enumerate(guide.get("breadcrumbs", []), start=1):
        if "endpoint" in crumb:
            path = url_for(crumb["endpoint"])
        else:
            path = crumb.get("url", "")
        items.append(
            {
                "@type": "ListItem",
                "position": position,
                "name": crumb["name"],
                "item": _absolute_url(url_root, path),
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def build_article_schema(guide: dict, canonical_url: str) -> dict:
    """Build Article schema for a guide."""
    last_modified = guide.get("last_modified")
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": guide.get("title"),
        "description": guide.get("meta_description"),
        "datePublished": last_modified,
        "dateModified": last_modified,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "author": {"@type": "Organization", "name": SITE_NAME},
        "publisher": {"@type": "Organization", "name": SITE_NAME},
    }
