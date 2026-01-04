# Zakat Calculator

A web application for calculating Zakat (Islamic wealth tax). This calculator helps Muslims determine their Zakat obligation based on their assets and the current Nisab threshold.

## Key Concepts

- **Zakat**: Islamic obligatory charity, calculated at 2.5% of eligible wealth
- **Nisab**: Minimum wealth threshold above which Zakat becomes obligatory
  - Gold Nisab: 85 grams
  - Silver Nisab: 595 grams
- **Hawl**: A lunar year must pass on the wealth before Zakat is due

## Prerequisites

- Docker
- Docker Compose v2

## Quick Start

Build and run the application:

```bash
docker compose up --build
```

The application will be available at http://localhost:8080

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

### GET /api/v1/pricing

Returns current pricing data for Zakat calculation.

**Response:**
```json
{
  "gold": {
    "price_per_gram_usd": 65.50,
    "nisab_grams": 85,
    "nisab_value_usd": 5567.50
  },
  "silver": {
    "price_per_gram_usd": 0.82,
    "nisab_grams": 595,
    "nisab_value_usd": 487.90
  },
  "currency": {
    "base": "USD",
    "rates": { ... }
  },
  "zakat_rate": 0.025,
  "last_updated": "2025-01-04T00:00:00Z"
}
```

## Development

### Project Structure

```
zakat-app/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes/
│   │   ├── main.py          # UI routes (/)
│   │   ├── health.py        # Health check (/healthz)
│   │   └── api.py           # API routes (/api/v1/*)
│   └── templates/
│       ├── base.html        # Base template
│       └── calculator.html  # Calculator UI
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_health.py       # Health endpoint tests
│   └── test_api.py          # API endpoint tests
├── Dockerfile
├── docker-compose.yml
├── gunicorn.conf.py
├── wsgi.py
├── pyproject.toml
└── requirements.txt
```

## License

MIT
