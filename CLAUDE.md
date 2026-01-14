# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zakat Calculator - A Flask web application for calculating Islamic wealth tax (Zakat). Calculates 2.5% obligation on wealth exceeding the Nisab threshold (85g gold or 595g silver).

## Common Commands

```bash
# Run the app locally
docker compose up --build

# Run pricing sync daemon (optional)
docker compose up pricing-sync

# When UI changes don't show, rebuild/recreate the web container
DOCKER_BUILDKIT=0 docker compose up --build -d web

# Local app URL
http://localhost:8080

# Run tests (all tests must pass before committing)
docker compose run --rm web pytest

# Run specific test file
docker compose run --rm web pytest tests/test_main.py -v

# Run single test
docker compose run --rm web pytest tests/test_main.py::test_calculator_returns_200 -v

# Initialize database and seed data
docker compose run --rm web flask init-db
docker compose run --rm web flask seed-all

# Import pricing data from CSV
docker compose run --rm web flask import-fx-csv data/seed/fx_rates.csv
docker compose run --rm web flask import-metals-csv data/seed/metal_prices.csv
docker compose run --rm web flask import-crypto-csv data/seed/crypto_prices.csv
```

## Architecture

### Flask App Factory Pattern
- `app/__init__.py`: `create_app()` factory configures Flask, registers blueprints, initializes DB
- Blueprints: `main_bp` (UI), `health_bp` (/healthz), `api_bp` (/api/v1/*)

### Pricing Data Flow (3-Tier Fallback)
The `SnapshotRepository` (`app/services/snapshot_repository.py`) implements read-through caching:
1. **SQLite** (local) → 2. **Cloudflare R2** (remote) → 3. **Upstream providers** (network)

Each successful fetch populates lower-tier caches. R2 is optional and best-effort.

### Pricing Sync Configuration
- `PRICING_ALLOW_NETWORK` gates network sync (app default: 0; docker compose default: 1)
- `PRICING_AUTO_SYNC` controls auto-sync; in-app thread requires `PRICING_BACKGROUND_SYNC=1`
- Daemon settings: `PRICING_SYNC_INTERVAL_SECONDS`, `PRICING_LOOKBACK_MONTHS`, `PRICING_RECENT_DAYS`, `PRICING_MONTHLY_LIMIT`
- Optional provider keys: `OPENEXCHANGERATES_APP_ID`, `GOLDAPI_KEY`, `METALPRICEAPI_KEY`, `METALS_DEV_API_KEY`, `COINMARKETCAP_API_KEY`
- R2 cache config uses `R2_*` env vars (`R2_ENABLED`, `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PREFIX`)

### Cadence System
Historical pricing uses tiered snapshot granularity (`app/services/cadence.py`):
- **Daily**: Last 30 days
- **Weekly**: Days 31-90 (Monday snapshots)
- **Monthly**: Beyond 90 days (1st of month)

### Calculation Engine
`app/services/calc.py` contains two calculation functions:
- `calculate_zakat()`: Legacy v1 format (gold, cash, bank only)
- `calculate_zakat_v2()`: Full format (adds metals, crypto, nisab basis selection)

Both use constants: `ZAKAT_RATE = 0.025`, `NISAB_GOLD_GRAMS = 85`, `NISAB_SILVER_GRAMS = 595`

### Key API Endpoints
- `GET /api/v1/pricing?date=YYYY-MM-DD&base=CAD` - Pricing snapshot with FX, metals, crypto
- `POST /api/v1/calculate` - Calculate zakat from asset list
- `GET /api/v1/currencies` - Currency list (CAD first, then high-volume, then alphabetical)

### Provider Selection Order
- FX: OpenExchangeRates (if key) → ExchangeRateAPI → Fallback
- Metals: MetalPriceAPI (if key) → GoldAPI (if key) → Metals.dev (if key) → Fallback
- Crypto: CoinMarketCap (if key) → CoinGecko → Fallback

### UI Routes & Content
- `/` - Calculator UI
- `/about-zakat` - About Zakat page
- `/faq` - FAQ page
- `/contact` - Contact page

#### Content Links
- Contribute button (global nav): https://buymeacoffee.com/zakatcalculator
- Contact email (only): info@whatismyzakat.com

### Test Fixtures
`tests/conftest.py` provides:
- `client`: Basic Flask test client
- `db_client`: Client with seeded SQLite database
- `frozen_time`: Freezes time to 2026-01-15 for deterministic cadence tests
- `fake_r2`: In-memory R2 mock for testing without network

### Frontend
Single-page calculator at `/` using vanilla JS. Key components in `app/static/js/`:
- `calculator.js`: Main calculation logic with live updates
- `components/currency-autocomplete.js`: 179 ISO 4217 currencies with compact mode
- `components/crypto-autocomplete.js`: Top 100 cryptocurrencies
- `components/nisab-indicator.js`: Visual nisab threshold indicator
- `components/share-link.js`: Shareable URL generation with LZ-string compression
- `components/csv-export.js`: Export assets to CSV

Templates in `app/templates/`:
- `base.html`: Shared layout + nav (includes Contribute button)
- `calculator.html`
- `about_zakat.html`
- `faq.html`
- `contact.html`

#### Currency Autocomplete Modes
- **Full mode** (base currency selector): Shows "CAD — Canadian Dollar"
- **Compact mode** (row-level selectors): Shows "$ — CAD" using CURRENCY_SYMBOLS map

#### Weight Units System
Per-row weight unit selection for gold/metal assets. Supported units in `WEIGHT_UNITS`:
- `g` (grams) - canonical storage unit
- `ozt` (troy ounces) - 31.1035g
- `tola` - 11.664g (South Asian)
- `vori` - 11.664g (Bengali, same as tola)
- `aana` - 0.729g (1/16 of tola, South Asian)

Weight is always stored/transmitted in grams; UI shows a "grams pill" with converted value.

### CSS Structure
- `app/static/css/autocomplete.css`: Currency/crypto autocomplete styling, compact mode
- `app/static/css/nisab-indicator.css`: Nisab threshold indicator card
- `app/static/css/tools.css`: Share link and export buttons
- `app/templates/base.html`: Main styles embedded (gradients, layout, responsive breakpoints)

### Responsive Layout (3 Viewport Modes)

| Mode | Width | Layout |
|------|-------|--------|
| **Full Desktop** | ≥1750px | Two-column, single-line asset rows, expanded field widths (200px for weight/amount) |
| **Compact Desktop** | 1280-1749px | Two-column, asset rows wrap to 2 lines, container uses `fit-content` for ad space |
| **Mobile/Tablet** | ≤1279px | Single-column stacked layout |

Additional mobile refinements at 1023px, 767px, 640px, 600px for progressively smaller screens.

### Pill Number Formatting
The `formatCompactPillNumber()` function in `calculator.js` prevents pill overflow:
- Values < 10,000: Show as `X.XX` (2 decimals)
- Values ≥ 10,000: Use suffixes `k` (thousand), `M` (million), `B` (billion), `T` (trillion)
- Examples: `9999.99`, `10.00k`, `123.46k`, `1.23M`, `1.23B`
- Handles NaN/null gracefully with em-dash `—`

Used by both purple value pills (`.base-value-pill`) and grams pills (`.weight-grams-pill`).

### Field Width Constraints
- **Weight fields**: 120px default, 200px in Full Desktop (18 chars)
- **Amount fields**: 130px default, 200px in Full Desktop (18 chars)
- **Crypto autocomplete**: 160px fixed width
- **Metal type selector**: 80px default, 120px in Full Desktop

## Testing Guidelines

- Every new endpoint needs a test
- No network calls in tests (use fixtures and fakes)
- Tests use frozen time (`FROZEN_TODAY = date(2026, 1, 15)`) for cadence determinism

## Git Workflow

### Branches
- `dev`: Active development branch (commit here first)
- `codex`: Mirror of dev for CI/automation
- `main`: Stable release branch
- `production`: Deployed to production server

### Typical Flow
1. Make changes on `dev`
2. Test locally with `docker compose up --build`
3. Commit and push to `dev`
4. Fast-forward merge to `codex`, `main`, `production` as needed

```bash
# Push to all branches
git checkout main && git merge dev && git push origin main
git checkout production && git merge dev && git push origin production
git checkout codex && git merge dev && git push origin codex
git checkout dev
```

## Key Patterns

### Asset Row Structure
Each asset type (gold, metal, cash, bank, crypto) uses `.asset-row` containers with:
- Name input (`.input-name`)
- Type-specific inputs (weight, amount, karat, etc.)
- Currency/crypto autocomplete (`.currency-autocomplete`, `.crypto-autocomplete`)
- Base value pill (`.base-value-pill`) showing converted value
- Remove button (`.btn-remove`)

### Live Calculation
`recalculate()` in calculator.js triggers on any input change, fetches pricing from `/api/v1/pricing`, and updates all value pills and totals in real-time.
