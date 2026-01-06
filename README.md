# Zakat Calculator

A web application for calculating Zakat (Islamic wealth tax). This calculator helps Muslims determine their Zakat obligation based on their assets and the current Nisab threshold.

## Key Concepts

- **Zakat**: Islamic obligatory charity, calculated at 2.5% of eligible wealth
- **Nisab**: Minimum wealth threshold above which Zakat becomes obligatory
  - Gold Nisab: 85 grams
  - Silver Nisab: 595 grams
- **Hawl**: A lunar year must pass on the wealth before Zakat is due

## Features

- **Live Calculations**: Totals update instantly as you type
- **Multi-Currency Support**: 179 ISO 4217 currencies with autocomplete
- **Historical Pricing**: Calculate zakat based on any historical date
- **Asset Categories**:
  - Gold (with karat purity: 24K, 22K, 21K, 18K, 14K, 10K, 9K)
  - Other Precious Metals (Silver, Platinum, Palladium)
  - Cash on Hand
  - Bank Accounts
  - Cryptocurrency (Top 100 by market cap)

## Prerequisites

- Docker
- Docker Compose v2

## Quick Start

Build and run the application:

```bash
docker compose up --build
```

The application will be available at http://localhost:8080

## Database Setup

Initialize the pricing database and seed data:

```bash
docker compose run --rm web flask init-db
docker compose run --rm web flask seed-all
```

Or import custom pricing data from CSV:

```bash
docker compose run --rm web flask import-fx-csv /path/to/fx_rates.csv
docker compose run --rm web flask import-metals-csv /path/to/metal_prices.csv
docker compose run --rm web flask import-crypto-csv /path/to/crypto_prices.csv
```

## Testing

Run the test suite:

```bash
docker compose run --rm web pytest
```

Run tests with verbose output:

```bash
docker compose run --rm web pytest -v
```

## API Endpoints

### GET /

Returns the Zakat Calculator web interface (HTML).

### GET /healthz

Health check endpoint for container orchestration.

**Response:**
```json
{
  "status": "ok"
}
```

### GET /api/v1/currencies

Returns the list of supported currencies with ordering (CAD first, then high-volume currencies, then alphabetical).

**Response:**
```json
{
  "currencies": [
    {"code": "CAD", "name": "Canadian Dollar", "minor_unit": 2},
    {"code": "USD", "name": "United States Dollar", "minor_unit": 2},
    ...
  ],
  "default": "CAD",
  "count": 179
}
```

### GET /api/v1/pricing

Returns pricing data for Zakat calculation with optional date and base currency parameters.

**Query Parameters:**
- `date` (optional): Historical date in YYYY-MM-DD format (defaults to today)
- `base` (optional): Base currency code (defaults to CAD)

**Response:**
```json
{
  "effective_date": "2025-01-01",
  "base_currency": "CAD",
  "fx_rates": {
    "USD": 1.38,
    "EUR": 1.52,
    ...
  },
  "metals": {
    "gold": {"price_per_gram": 89.70, "price_per_oz": 2789.46},
    "silver": {"price_per_gram": 1.17, "price_per_oz": 36.48},
    "platinum": {"price_per_gram": 44.16, "price_per_oz": 1373.00},
    "palladium": {"price_per_gram": 48.30, "price_per_oz": 1502.00}
  },
  "crypto": {
    "BTC": {"name": "Bitcoin", "price": 69000.00, "rank": 1},
    "ETH": {"name": "Ethereum", "price": 4140.00, "rank": 2},
    ...
  },
  "coverage": {
    "fx_exact": true,
    "metals_exact": true,
    "crypto_exact": false
  },
  "request": {"date": "2025-01-01", "base": "CAD"}
}
```

### GET /api/v1/pricing/legacy

Returns pricing data in the legacy format (for backward compatibility).

### POST /api/v1/calculate

Calculate Zakat based on provided assets. Supports both legacy and v2 formats.

**V2 Request (recommended):**
```json
{
  "base_currency": "CAD",
  "calculation_date": "2025-01-01",
  "gold_items": [
    {"name": "Ring", "weight_grams": 10, "purity_karat": 22}
  ],
  "cash_items": [
    {"name": "Wallet", "amount": 500, "currency": "CAD"}
  ],
  "bank_items": [
    {"name": "Savings", "amount": 10000, "currency": "CAD"}
  ],
  "metal_items": [
    {"name": "Silver coins", "metal": "silver", "weight_grams": 100}
  ],
  "crypto_items": [
    {"name": "Bitcoin", "symbol": "BTC", "amount": 0.5}
  ]
}
```

**V2 Response:**
```json
{
  "base_currency": "CAD",
  "subtotals": {
    "gold": {"items": [...], "total_pure_grams": 9.17, "total": 822.50},
    "cash": {"items": [...], "total": 500.00},
    "bank": {"items": [...], "total": 10000.00},
    "metals": {"items": [...], "total": 117.00},
    "crypto": {"items": [...], "total": 34500.00}
  },
  "grand_total": 45939.50,
  "nisab": {
    "gold_grams": 85,
    "gold_value": 7624.50,
    "silver_grams": 595,
    "silver_value": 697.35,
    "threshold_used": 697.35
  },
  "above_nisab": true,
  "zakat_due": 1148.49,
  "zakat_rate": 0.025
}
```

**Legacy Request:**
```json
{
  "master_currency": "CAD",
  "gold": [...],
  "cash": [...],
  "bank": [...]
}
```

## R2 Remote Cache (Optional)

The app supports Cloudflare R2 as a shared remote cache for pricing snapshots.
This allows multiple deployments to share pricing data without each hitting
upstream providers.

### Setup

1. Create a Cloudflare R2 bucket
2. Create an API token with R2 read/write permissions
3. Set environment variables:

```bash
R2_ENABLED=1
R2_BUCKET=your-bucket-name
R2_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key
R2_PREFIX=zakat-app/pricing/  # optional
```

### How It Works

- Pricing snapshots are stored as gzip-compressed JSON in R2
- Key format: `{prefix}pricing/{type}/{cadence}/{date}.json.gz`
- Lookup order: SQLite (local) -> R2 (remote) -> Upstream provider
- New upstream fetches are automatically mirrored to R2
- R2 is best-effort; failures don't break the app

### Security Notes

- R2 credentials are read from environment variables only
- Credentials are never logged
- R2 bucket should be private (no public access)
- Only pricing data is stored (no user data)

## Development

### Project Structure

```
zakat-app/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── db.py                # SQLite database connection
│   ├── cli.py               # Flask CLI commands
│   ├── data/
│   │   ├── currencies.py    # ISO 4217 currency list
│   │   ├── crypto.py        # Top 100 cryptocurrencies
│   │   └── metals.py        # Supported precious metals
│   ├── routes/
│   │   ├── main.py          # UI routes (/)
│   │   ├── health.py        # Health check (/healthz)
│   │   └── api.py           # API routes (/api/v1/*)
│   ├── services/
│   │   ├── calc.py          # Zakat calculation logic
│   │   ├── fx.py            # Currency conversion
│   │   ├── pricing.py       # Price fetching
│   │   └── db_pricing.py    # Database pricing queries
│   ├── static/
│   │   ├── css/
│   │   │   └── autocomplete.css
│   │   └── js/
│   │       ├── calculator.js
│   │       └── components/
│   │           ├── currency-autocomplete.js
│   │           └── crypto-autocomplete.js
│   └── templates/
│       ├── base.html        # Base template
│       └── calculator.html  # Calculator UI
├── data/
│   ├── seed/                # Seed data CSV files
│   └── pricing.sqlite       # SQLite pricing database
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_health.py       # Health endpoint tests
│   ├── test_api.py          # API endpoint tests
│   ├── test_calculate.py    # Calculate endpoint tests
│   ├── test_currencies.py   # Currency endpoint tests
│   └── test_services/       # Service layer tests
├── Dockerfile
├── docker-compose.yml
├── gunicorn.conf.py
├── wsgi.py
├── pyproject.toml
└── requirements.txt
```

### CLI Commands

```bash
# Initialize database schema
flask init-db

# Import seed data
flask seed-all

# Import FX rates from CSV
flask import-fx-csv data/seed/fx_rates.csv

# Import metal prices from CSV
flask import-metals-csv data/seed/metal_prices.csv

# Import crypto prices from CSV
flask import-crypto-csv data/seed/crypto_prices.csv
```

## License

MIT
