# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zakat Calculator - A Flask web application for calculating Islamic wealth tax (Zakat). Calculates 2.5% obligation on wealth exceeding the Nisab threshold (85g gold or 595g silver).

## Common Commands

```bash
# Run the app locally
docker compose up --build

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

### Test Fixtures
`tests/conftest.py` provides:
- `client`: Basic Flask test client
- `db_client`: Client with seeded SQLite database
- `frozen_time`: Freezes time to 2026-01-15 for deterministic cadence tests
- `fake_r2`: In-memory R2 mock for testing without network

### Frontend
Single-page calculator at `/` using vanilla JS. Key components in `app/static/js/`:
- `calculator.js`: Main calculation logic with live updates
- `components/currency-autocomplete.js`: 179 ISO 4217 currencies
- `components/crypto-autocomplete.js`: Top 100 cryptocurrencies

## Testing Guidelines

- Every new endpoint needs a test
- No network calls in tests (use fixtures and fakes)
- Tests use frozen time (`FROZEN_TODAY = date(2026, 1, 15)`) for cadence determinism
