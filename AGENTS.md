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
```

## File Structure

```
app/
├── __init__.py              # create_app() factory
├── routes/
│   ├── main.py              # UI routes (/)
│   ├── api.py               # REST API (/api/v1/*)
│   └── health.py            # Health check (/healthz)
├── services/
│   ├── background_sync.py   # Optional in-app pricing sync thread
│   ├── calc.py              # Zakat calculation logic
│   ├── cadence.py           # Date snapshot granularity
│   ├── config.py            # Env-based pricing config + API keys
│   ├── providers/           # FX/metal/crypto providers + registry
│   ├── r2_client.py         # Cloudflare R2 cache client
│   ├── r2_config.py         # R2 env config
│   ├── snapshot_repository.py  # 3-tier pricing cache
│   └── sync.py              # Provider sync service + R2 mirroring
├── static/
│   ├── js/
│   │   ├── calculator.js    # Main frontend logic
│   │   └── components/      # Autocomplete, indicators
│   └── css/                 # Stylesheets
└── templates/               # Jinja2 templates
    ├── base.html            # Shared layout + nav (includes Contribute button)
    ├── calculator.html
    ├── about_zakat.html
    ├── faq.html
    └── contact.html

scripts/
└── pricing_sync_daemon.py   # Background pricing sync service

tests/
├── conftest.py              # Fixtures (client, db_client, frozen_time)
└── test_*.py                # Test files
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
- Daemon service uses `PRICING_SYNC_INTERVAL_SECONDS`, `PRICING_LOOKBACK_MONTHS`, `PRICING_RECENT_DAYS`, `PRICING_MONTHLY_LIMIT` (optional).
- Provider API keys (optional): `OPENEXCHANGERATES_APP_ID`, `GOLDAPI_KEY`, `METALPRICEAPI_KEY`, `METALS_DEV_API_KEY`, `COINMARKETCAP_API_KEY`.
- R2 cache config uses `R2_*` env vars (`R2_ENABLED`, `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PREFIX`).

## UI Routes & Content

| Path | Description |
|------|-------------|
| `/` | Calculator UI |
| `/about-zakat` | About Zakat page |
| `/faq` | FAQ page |
| `/contact` | Contact page |

### Content Links
- Contribute button (global nav): `https://buymeacoffee.com/zakatcalculator`
- Contact email (only): `info@whatismyzakat.com`

## Frontend Patterns

### Asset Rows
```html
<div class="asset-row" data-type="gold|metal|cash|bank|crypto">
    <input class="input-name" />
    <!-- type-specific inputs -->
    <div class="currency-autocomplete"></div>
    <span class="base-value-pill"></span>
    <button class="btn-remove">−</button>
</div>
```

### Currency Autocomplete
- Full mode: `"CAD — Canadian Dollar"` (base currency selector)
- Compact mode: `"$ — CAD"` (row-level selectors)

### Live Calculation
`recalculate()` triggers on input change → fetches `/api/v1/pricing` → updates pills and totals.

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
