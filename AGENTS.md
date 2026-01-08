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

# Database
docker compose run --rm web flask init-db
docker compose run --rm web flask seed-all
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
│   ├── calc.py              # Zakat calculation logic
│   ├── cadence.py           # Date snapshot granularity
│   └── snapshot_repository.py  # 3-tier pricing cache
├── static/
│   ├── js/
│   │   ├── calculator.js    # Main frontend logic
│   │   └── components/      # Autocomplete, indicators
│   └── css/                 # Stylesheets
└── templates/               # Jinja2 templates

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
