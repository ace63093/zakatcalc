# AGENTS.md

Guidelines for AI coding agents (Codex, Copilot, etc.) working on this repository.

**For full architecture, patterns, and configuration details, see [CLAUDE.md](CLAUDE.md).** This file contains only the quick-reference essentials.

## Project

Zakat Calculator - Flask web app for Islamic wealth tax calculation (2.5% on wealth exceeding Nisab threshold: 85g gold or 595g silver). Served on multiple domains (.com, .ca, .net, .org) with canonical tags pointing to `.com`.

## Commands

```bash
# Development
docker compose up --build              # Run locally (http://localhost:8080)
docker compose run --rm web pytest     # Run all tests (MUST pass before commit)
docker compose run --rm web pytest tests/test_main.py -v  # Single file

# Database
docker compose run --rm web flask init-db
docker compose run --rm web flask seed-all

# R2 data management
docker compose run --rm web flask mirror-to-r2      # Mirror SQLite pricing to R2
docker compose run --rm web flask backfill-r2        # Backfill R2 with cadence-aware data

# Geolocation
docker compose run --rm web flask refresh-geodb
```

## File Structure

```
app/
├── __init__.py              # create_app() + CF-Connecting-IP + visitor logging hook
├── routes/
│   ├── main.py              # UI routes (/, /about-zakat, /faq, /contact, etc.)
│   ├── api.py               # REST API (/api/v1/pricing, /calculate, /visitors)
│   ├── health.py            # /healthz
│   └── guides.py            # SEO guides (/guides, /<slug>, /sitemap.xml, /robots.txt)
├── content/
│   └── guides.py            # GUIDES dict (12 guide slugs + content)
├── services/
│   ├── calc.py / advanced_calc.py  # Zakat calculation (v1/v2/v3)
│   ├── config.py            # Env-based config + feature flags
│   ├── seo.py               # JSON-LD schema builders (article, breadcrumb, FAQ)
│   ├── geolocation.py       # IP geolocation (GeoIndex, Apple CSV, R2/SQLite)
│   ├── geodb_sync.py        # Background geodb refresh + visitor R2 backup
│   ├── visitor_logging.py   # Visitor upsert (plain IP), R2 backup/restore
│   ├── snapshot_repository.py  # 3-tier pricing cache (SQLite → R2 → upstream)
│   └── r2_client.py         # Cloudflare R2 client
├── static/js/
│   ├── calculator.js        # Main frontend (getState/setState)
│   ├── cad_to_bdt.js        # CAD→BDT converter logic
│   ├── utils/shared.js      # Shared constants (NISAB, ZAKAT_RATE, WEIGHT_UNITS)
│   ├── vendor/lz-string.min.js  # LZ-string compression library
│   └── components/          # autosave, share-link, date-assistant, etc.
├── static/css/
│   ├── variables.css        # CSS custom properties
│   ├── autocomplete.css     # Currency/crypto autocomplete
│   ├── cad_to_bdt.css       # CAD→BDT converter styles
│   └── ...                  # nisab-indicator, tools, advanced-assets, etc.
└── templates/               # Jinja2 templates (feature-flagged sections)
    ├── guide.html / guides_index.html  # SEO guides templates
    └── ...                  # calculator, about, faq, contact, summary, etc.

scripts/
└── pricing_sync_daemon.py   # Standalone pricing sync daemon (docker compose up pricing-sync)

tests/
├── conftest.py              # Fixtures (client, db_client, frozen_time, fake_r2)
├── fakes/fake_r2.py         # In-memory R2 mock
├── test_geolocation.py      # 24 tests
├── test_visitor_logging.py  # Visitor logging + R2 backup/restore tests
├── test_guides_pages.py     # Guides blueprint tests
├── test_sitemap_and_robots.py  # Sitemap/robots.txt tests
├── test_selenium_local.py   # 33 Selenium tests (--noconftest)
├── test_selenium_multihost.py # 32 multi-domain tests (.com/.ca/.net/.org)
├── test_selenium_live.py    # Production live tests
└── test_services/           # calc, pricing, R2, sync tests
```

## Key Constants

```python
ZAKAT_RATE = 0.025           # 2.5%
NISAB_GOLD_GRAMS = 85        # Gold threshold
NISAB_SILVER_GRAMS = 595     # Silver threshold
```

## Testing Rules

1. Every endpoint needs a test
2. No network calls (use fixtures)
3. Use `FROZEN_TODAY = date(2026, 1, 15)` for time-dependent tests
4. Unit tests: `docker compose run --rm web pytest` (349 tests)
5. Selenium local: `python3 -m pytest tests/test_selenium_local.py -v --noconftest`
6. Selenium live: `pytest tests/test_selenium_live.py -v`
7. Selenium multi-domain: `python3 -m pytest tests/test_selenium_multihost.py -v --noconftest`

## Git Branches

| Branch | Purpose |
|--------|---------|
| `dev` | Active development (commit here first) |
| `codex` | CI/automation mirror |
| `main` | Stable releases |
| `production` | Deployed |

## Do Not

- Make network calls in tests
- Commit without running `pytest`
- Push directly to `main` or `production` without merging from `dev`
- Add dependencies without updating `requirements.txt`
