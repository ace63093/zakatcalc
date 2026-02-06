# AGENTS.md

Guidelines for AI coding agents (Codex, Copilot, etc.) working on this repository.

## Project

Zakat Calculator - Flask web app for Islamic wealth tax calculation (2.5% on wealth exceeding Nisab threshold: 85g gold or 595g silver).

## Commands

```bash
# Development
docker compose up --build              # Run locally
docker compose run --rm web pytest     # Run all tests (MUST pass before commit)
docker compose run --rm web pytest tests/test_main.py -v  # Single file
docker compose up pricing-sync         # Run pricing sync daemon (optional)

# When UI changes don't show, rebuild/recreate the web container
DOCKER_BUILDKIT=0 docker compose up --build -d web

# Local app URL
http://localhost:8080

# Database
docker compose run --rm web flask init-db
docker compose run --rm web flask seed-all

# Import pricing data from CSV
docker compose run --rm web flask import-fx-csv data/seed/fx_rates.csv
docker compose run --rm web flask import-metals-csv data/seed/metal_prices.csv
docker compose run --rm web flask import-crypto-csv data/seed/crypto_prices.csv

# One-time FX backfill from Fawaz (writes to SQLite + R2)
# Note: Fawaz historical availability starts around 2024-04-01.
docker compose run --rm web python scripts/backfill_fx_fawaz.py --start 2024-04-01 --end 2025-12-31 --daily
```

## File Structure

```
app/
├── __init__.py              # create_app() factory
├── constants.py             # Shared constants (NISAB, ZAKAT_RATE, etc.)
├── routes/
│   ├── main.py              # UI routes (/, /methodology, /summary, etc.)
│   ├── api.py               # REST API (/api/v1/*) - supports v1/v2/v3 calculation
│   └── health.py            # Health check (/healthz)
├── services/
│   ├── advanced_calc.py     # Advanced zakat calculation (v3: stocks, retirement, etc.)
│   ├── background_sync.py   # Optional in-app pricing sync thread
│   ├── calc.py              # Core zakat calculation (v1/v2)
│   ├── cadence.py           # Date snapshot granularity
│   ├── config.py            # Env-based config + feature flags
│   ├── providers/           # FX/metal/crypto providers + registry
│   ├── r2_client.py         # Cloudflare R2 cache client
│   ├── r2_config.py         # R2 env config
│   ├── snapshot_repository.py  # 3-tier pricing cache
│   └── sync.py              # Provider sync service + R2 mirroring
├── static/
│   ├── js/
│   │   ├── calculator.js    # Main frontend logic (getState/setState for serialize)
│   │   ├── utils/shared.js  # Shared constants and utilities
│   │   └── components/
│   │       ├── autosave.js          # LocalStorage autosave (debounced 2s)
│   │       ├── currency-autocomplete.js  # 179 ISO currencies
│   │       ├── crypto-autocomplete.js    # Top 100 cryptos
│   │       ├── csv-export.js        # CSV export
│   │       ├── date-assistant.js    # Zakat anniversary tracker + Hijri + ICS
│   │       ├── nisab-indicator.js   # Nisab threshold card
│   │       ├── share-link.js        # LZ-string compressed share URLs (#data=)
│   │       └── summary.js          # Client-side printable summary
│   └── css/
│       ├── autocomplete.css         # Currency/crypto dropdowns
│       ├── advanced-assets.css      # Advanced mode sections
│       ├── content-pages.css        # About, FAQ, methodology, contact pages
│       ├── date-assistant.css       # Date assistant component
│       ├── nisab-indicator.css      # Nisab card
│       ├── summary.css              # Print-optimized summary
│       └── tools.css                # Share link modal, autosave toast
└── templates/
    ├── base.html            # Shared layout + nav
    ├── calculator.html      # Main calculator (feature-flagged sections)
    ├── about_zakat.html
    ├── methodology.html     # Calculation methodology (JSON-LD Article)
    ├── faq.html             # FAQ (JSON-LD FAQPage)
    ├── contact.html
    ├── summary.html         # Printable summary (client-side render)
    └── feature_disabled.html

scripts/
├── pricing_sync_daemon.py   # Background pricing sync service
└── backfill_fx_fawaz.py     # One-time FX backfill (Fawaz)

tests/
├── conftest.py              # Fixtures (client, db_client, frozen_time)
├── test_main.py             # Route tests (16 tests including methodology)
├── test_selenium_live.py    # Selenium tests against production
├── test_selenium_local.py   # Selenium tests against localhost (33 tests)
└── test_services/
    ├── test_advanced_calc.py  # Advanced calculation tests (22 tests)
    ├── test_fx_providers.py   # FX provider tests
    └── test_r2_client.py      # R2 caching tests
```

## Key Constants

```python
ZAKAT_RATE = 0.025           # 2.5%
NISAB_GOLD_GRAMS = 85        # Gold threshold
NISAB_SILVER_GRAMS = 595     # Silver threshold
```

## Weight Units

```javascript
WEIGHT_UNITS = {
    'g': 1,              // grams (canonical)
    'ozt': 31.1035,      // troy ounces
    'tola': 11.664,      // South Asian
    'vori': 11.664,      // Bengali (same as tola)
    'aana': 0.729        // 1/16 tola
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/pricing?date=YYYY-MM-DD&base=CAD` | Pricing snapshot |
| POST | `/api/v1/calculate` | Calculate zakat |
| GET | `/api/v1/currencies` | Currency list |
| GET | `/api/v1/cryptocurrencies` | Crypto list |

## Pricing Sync & Config

- Network sync is gated by `PRICING_ALLOW_NETWORK` (app default: 0; docker compose default: 1).
- Auto-sync is controlled by `PRICING_AUTO_SYNC`; in-app thread requires `PRICING_BACKGROUND_SYNC=1`.
- `PRICING_SYNC_INTERVAL_SECONDS` controls auto-sync cadence (default 21600 = 6h; 86400 = daily).
- Daemon service uses `PRICING_SYNC_INTERVAL_SECONDS`, `PRICING_LOOKBACK_MONTHS`, `PRICING_RECENT_DAYS`, `PRICING_MONTHLY_LIMIT` (optional).
- Provider API keys (optional): `OPENEXCHANGERATES_APP_ID`, `GOLDAPI_KEY`, `METALPRICEAPI_KEY`, `METALS_DEV_API_KEY`, `COINMARKETCAP_API_KEY`.
- R2 cache config uses `R2_*` env vars (`R2_ENABLED`, `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PREFIX`).
- FX provider order: OpenExchangeRates (if key) → ExchangeRateAPI (latest) with Fawaz fallback for historical/missing.

## Feature Flags

Controlled by env vars in `app/services/config.py` via `get_feature_flags()`:

| Flag | Default | Controls |
|------|---------|----------|
| `ENABLE_ADVANCED_ASSETS` | 1 | Advanced assets mode (stocks, retirement, etc.) |
| `ENABLE_DATE_ASSISTANT` | 1 | Zakat date assistant in results sidebar |
| `ENABLE_AUTOSAVE` | 1 | LocalStorage autosave/restore |
| `ENABLE_PRINT_SUMMARY` | 1 | Print summary button and `/summary` route |

## UI Routes & Content

| Path | Description |
|------|-------------|
| `/` | Calculator UI |
| `/cad-to-bdt` | Hidden CAD→BDT converter (no nav link) |
| `/about-zakat` | About Zakat page |
| `/methodology` | Calculation methodology (JSON-LD Article schema) |
| `/faq` | FAQ page (JSON-LD FAQPage schema) |
| `/contact` | Contact page |
| `/summary` | Printable summary (data in URL fragment, client-side render) |
| `/privacy-policy` | Privacy policy page |

### Content Links
- Contribute button (global nav): `https://buymeacoffee.com/zakatcalculator`
- Contact email (only): `info@whatismyzakat.com`

## Frontend Patterns

### Asset Rows
```html
<div class="asset-row" data-type="gold|metal|cash|bank|crypto|credit_card|loan">
    <input class="input-name" />
    <!-- type-specific inputs -->
    <div class="currency-autocomplete"></div>
    <span class="base-value-pill"></span>
    <button class="btn-remove">−</button>
</div>
```

### Advanced Asset Rows (behind toggle)
```html
<div class="asset-row" data-type="stock|retirement|receivable|property|payable">
    <!-- type-specific inputs with valuation/accessibility selectors -->
</div>
```

### State Management
- `ZakatCalculator.getState()` → serializes all form data to JSON object
- `ZakatCalculator.setState(data)` → restores form from JSON object
- Used by share-link (LZ-compressed in `#data=` URL fragment) and autosave (localStorage)
- Schema version 2 with v1→v2 migration for backward compatibility

### Currency Autocomplete
- Full mode: `"CAD — Canadian Dollar"` (base currency selector)
- Compact mode: `"$ — CAD"` (row-level selectors)

### Live Calculation
`recalculate()` triggers on input change → fetches `/api/v1/pricing` → updates pills and totals.

### Autosave
- `Autosave.init(true)` called after calculator init
- Saves to `zakatCalculator_autosave` localStorage key (debounced 2s)
- Skips restore when share-link (`#data=`) present in URL
- Shows toast with "Clear" option on restore

### Pill Number Formatting
`formatCompactPillNumber()` prevents overflow: values < 10,000 show as `X.XX`, larger values use `k/M/B/T` suffixes.

## Responsive Breakpoints

| Mode | Width | Behavior |
|------|-------|----------|
| Full Desktop | ≥1750px | Two-column, single-line rows, 200px weight/amount fields |
| Compact Desktop | 1280-1749px | Two-column, rows wrap, `fit-content` container |
| Mobile | ≤1279px | Single-column stacked |

Additional breakpoints: 1023px, 767px, 640px, 600px.

## Testing Rules

1. Every endpoint needs a test
2. No network calls (use fixtures)
3. Use `FROZEN_TODAY = date(2026, 1, 15)` for time-dependent tests
4. Unit tests: `docker compose run --rm web pytest` (318 tests)
5. Selenium local: `python3 -m pytest tests/test_selenium_local.py -v --noconftest` (33 tests, needs `docker compose up --build -d web` running)
6. Selenium live: `pytest tests/test_selenium_live.py -v` (against production)

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
