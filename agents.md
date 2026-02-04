# agents.md

Instructions for AI coding agents (Codex, Claude, Copilot, etc.) working on this repository.

## Project Overview

**Zakat Calculator** - Flask web app for calculating Islamic wealth tax (Zakat). Calculates 2.5% on wealth exceeding Nisab threshold (85g gold or 595g silver).

**Production URL**: https://whatismyzakat.com

## Quick Reference

### Run Locally
```bash
docker compose up --build          # Start app at http://localhost:8080
docker compose up pricing-sync     # Run pricing sync daemon
```

### Test Commands
```bash
docker compose run --rm web pytest                           # All tests
docker compose run --rm web pytest tests/test_main.py -v     # Specific file
docker compose run --rm web pytest tests/test_main.py::test_name -v  # Single test
```

### Database Commands
```bash
docker compose run --rm web flask init-db      # Initialize database
docker compose run --rm web flask seed-all     # Seed with sample data
docker compose run --rm web flask sync-prices --start YYYY-MM-DD --end YYYY-MM-DD  # Sync pricing
```

## Architecture

### Project Structure
```
app/
├── __init__.py              # create_app() factory
├── cli.py                   # Flask CLI commands
├── db.py                    # SQLite database
├── routes/
│   ├── main.py              # UI routes (/, /about-zakat, /faq, /contact)
│   ├── api.py               # REST API (/api/v1/*)
│   └── health.py            # Health check (/healthz)
├── services/
│   ├── calc.py              # Zakat calculation engine
│   ├── sync.py              # Pricing sync service
│   ├── cadence.py           # Snapshot cadence (daily/weekly/monthly)
│   ├── snapshot_repository.py  # 3-tier cache (SQLite → R2 → upstream)
│   └── providers/           # FX, metals, crypto data providers
├── static/
│   ├── js/calculator.js     # Main frontend logic
│   └── js/components/       # Currency/crypto autocomplete, etc.
└── templates/               # Jinja2 templates
tests/
├── conftest.py              # Fixtures (client, db_client, frozen_time)
└── test_*.py                # Test files
```

### Key Constants (app/services/calc.py)
```python
ZAKAT_RATE = 0.025           # 2.5%
NISAB_GOLD_GRAMS = 85        # Gold nisab threshold
NISAB_SILVER_GRAMS = 595     # Silver nisab threshold
```

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/pricing?date=YYYY-MM-DD&base=CAD` | Get pricing snapshot |
| POST | `/api/v1/calculate` | Calculate zakat from assets |
| GET | `/api/v1/currencies` | List supported currencies |
| POST | `/api/v1/pricing/sync` | Trigger pricing sync |
| GET | `/api/v1/pricing/sync-status` | Get sync status |

### Calculation Request (POST /api/v1/calculate)
```json
{
  "base_currency": "CAD",
  "calculation_date": "2026-01-15",
  "nisab_basis": "gold",
  "gold_items": [{"name": "Ring", "weight_grams": 10, "purity_karat": 22}],
  "cash_items": [{"name": "Wallet", "amount": 500, "currency": "CAD"}],
  "bank_items": [{"name": "Savings", "amount": 10000, "currency": "USD"}],
  "metal_items": [{"name": "Silver", "metal": "silver", "weight_grams": 500}],
  "crypto_items": [{"name": "BTC", "symbol": "BTC", "amount": 0.5}],
  "credit_card_items": [{"name": "Visa", "amount": 2000, "currency": "CAD"}],
  "loan_items": [{"name": "Car", "payment_amount": 500, "currency": "CAD", "frequency": "monthly"}]
}
```

### Pricing Data Flow
1. **SQLite** (local cache) → 2. **Cloudflare R2** (remote cache) → 3. **Upstream providers**

### Cadence System
- **Daily**: Last 30 days
- **Weekly**: Days 31-90 (Monday snapshots)
- **Monthly**: Beyond 90 days (1st of month)

### Debt Calculation
- `assets_total` = gold + metals + cash + bank + crypto
- `debts_total` = credit cards + annualized loans
- `net_total` = max(0, assets_total - debts_total)
- Zakat = net_total × 0.025 (if net_total ≥ nisab)

**Loan Frequency Multipliers**: weekly=52, biweekly=26, semi_monthly=24, monthly=12, quarterly=4, yearly=1

## Frontend

### JavaScript Components (app/static/js/)
- `calculator.js` - Main logic, live recalculation
- `components/currency-autocomplete.js` - 179 ISO 4217 currencies
- `components/crypto-autocomplete.js` - Top 100 cryptocurrencies
- `components/nisab-indicator.js` - Visual threshold indicator + conversion rates
- `components/share-link.js` - Shareable URLs (LZ-string compression)
- `components/csv-export.js` - Export to CSV

### Conversion Rates Display
Expandable section in Nisab Indicator showing rates for entered assets only:
- Metals: `Gold C$95.23/g`
- FX: `1 USD 1.35 CAD` (flips if rate < 1)
- Crypto: `BTC C$92,000.00`

### Weight Units
| Unit | Grams | Region |
|------|-------|--------|
| g | 1 | Universal |
| ozt | 31.1035 | Troy ounce |
| tola | 11.664 | South Asian |
| vori | 11.664 | Bengali |
| aana | 0.729 | 1/16 tola |

### Responsive Breakpoints
- **≥1750px**: Full desktop (two-column, expanded fields)
- **1280-1749px**: Compact desktop (two-column, wrapped rows)
- **≤1279px**: Mobile/tablet (single-column)

## Testing Guidelines

1. Every new endpoint needs a test
2. No network calls in tests (use fixtures)
3. Tests use frozen time: `FROZEN_TODAY = date(2026, 1, 15)`
4. Run `pytest` before committing

### Test Fixtures (tests/conftest.py)
- `client` - Basic Flask test client
- `db_client` - Client with seeded database
- `frozen_time` - Time frozen to 2026-01-15
- `fake_r2` - In-memory R2 mock

## Git Workflow

### Branches
- `dev` - Active development (commit here first)
- `main` - Stable release
- `production` - Deployed to Digital Ocean
- `codex` - CI/automation mirror

### Push to All Branches
```bash
git checkout main && git merge dev && git push origin main
git checkout production && git merge dev && git push origin production
git checkout codex && git merge dev && git push origin codex
git checkout dev
```

## Environment Variables

### Required for Sync
- `PRICING_ALLOW_NETWORK=1` - Enable network sync

### Optional Provider Keys
- `OPENEXCHANGERATES_APP_ID` - FX rates
- `METALPRICEAPI_KEY` - Metal prices
- `GOLDAPI_KEY` - Gold prices
- `METALS_DEV_API_KEY` - Metals.dev
- `COINMARKETCAP_API_KEY` - Crypto prices

### R2 Cache (Optional)
- `R2_ENABLED`, `R2_BUCKET`, `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PREFIX`

### SEO
- `CANONICAL_HOST` - Canonical domain for `<link rel="canonical">` and `og:url` (default: `whatismyzakat.com`)

## Common Tasks

### Fix Missing Pricing Data
```bash
docker compose run --rm web flask sync-prices --start 2026-01-27 --end 2026-01-31
```

### Check Pricing Sync Status
```bash
curl https://whatismyzakat.com/api/v1/pricing/sync-status
```

### Restart Pricing Daemon
```bash
docker compose restart pricing-sync
docker compose logs --tail=50 pricing-sync
```

## Contact
- Email: info@whatismyzakat.com
- Donate: https://buymeacoffee.com/zakatcalculator
