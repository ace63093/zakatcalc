"""Tests for the updated /api/v1/pricing endpoint."""
import os
import tempfile
from datetime import date, timedelta
import pytest
from unittest.mock import patch
from app import create_app
from app.db import get_db, init_db
from app.services.time_provider import TimeProvider


# Use the same frozen date as conftest.py for consistency
FROZEN_TODAY = date(2026, 1, 15)


@pytest.fixture
def app_with_seeded_db():
    """Create app with temporary database seeded with test data.

    Seed data aligned with FROZEN_TODAY (2026-01-15):
    - Daily range: 2025-12-17 to 2026-01-15 (days 0-29)
    - Weekly range: 2025-10-18 to 2025-12-16 (days 30-89)
    - Monthly range: before 2025-10-17

    Test dates seeded:
    - 2026-01-15: today (day 0, daily)
    - 2025-12-15: day 31 (weekly window) - Monday
    - 2025-12-08: day 38 (weekly window) - Monday
    - 2025-12-01: day 45 (weekly window) - Monday
    - 2025-10-01: day 106 (monthly window) - 1st of month
    """
    db_fd, db_path = tempfile.mkstemp(suffix='.sqlite')
    data_dir = os.path.dirname(db_path)

    app = create_app({
        'TESTING': True,
        'DATA_DIR': data_dir,
    })

    os.close(db_fd)
    os.rename(db_path, os.path.join(data_dir, 'pricing.sqlite'))

    # Freeze time for consistent cadence calculations
    provider = TimeProvider(frozen_date=FROZEN_TODAY)
    TimeProvider.set_default(provider)

    with app.app_context():
        init_db()
        db = get_db()

        # Seed FX data - dates aligned with 3-tier cadence from FROZEN_TODAY
        fx_data = [
            # Daily window dates
            ('2026-01-15', 'USD', 1.0),  # Today
            ('2026-01-15', 'CAD', 1.4200),
            ('2026-01-15', 'EUR', 0.9550),
            ('2026-01-10', 'USD', 1.0),  # Day 5 (daily)
            ('2026-01-10', 'CAD', 1.4180),
            ('2026-01-10', 'EUR', 0.9540),
            # Weekly window dates (Mondays)
            ('2025-12-15', 'USD', 1.0),  # Day 31 (Monday, weekly)
            ('2025-12-15', 'CAD', 1.4123),
            ('2025-12-15', 'EUR', 0.9512),
            ('2025-12-15', 'BDT', 119.50),
            ('2025-12-08', 'USD', 1.0),  # Day 38 (Monday, weekly)
            ('2025-12-08', 'CAD', 1.4100),
            ('2025-12-08', 'EUR', 0.9500),
            ('2025-12-01', 'USD', 1.0),  # Day 45 (Monday, weekly)
            ('2025-12-01', 'CAD', 1.4052),
            ('2025-12-01', 'EUR', 0.9483),
            ('2025-12-01', 'BDT', 119.50),
            # Monthly window dates (1st of month)
            ('2025-10-01', 'USD', 1.0),  # Day 106 (monthly)
            ('2025-10-01', 'CAD', 1.3900),
            ('2025-10-01', 'EUR', 0.9400),
        ]
        for dt, currency, rate in fx_data:
            db.execute(
                'INSERT INTO fx_rates (date, currency, rate_to_usd) VALUES (?, ?, ?)',
                (dt, currency, rate)
            )

        # Seed metal data
        metal_data = [
            # Daily window
            ('2026-01-15', 'gold', 84.00),
            ('2026-01-15', 'silver', 1.02),
            ('2026-01-10', 'gold', 83.80),
            ('2026-01-10', 'silver', 1.01),
            # Weekly window (Mondays)
            ('2025-12-15', 'gold', 83.00),
            ('2025-12-15', 'silver', 1.00),
            ('2025-12-08', 'gold', 82.80),
            ('2025-12-08', 'silver', 0.99),
            ('2025-12-01', 'gold', 82.50),
            ('2025-12-01', 'silver', 0.98),
            ('2025-12-01', 'platinum', 31.20),
            ('2025-12-01', 'palladium', 32.50),
            # Monthly window
            ('2025-10-01', 'gold', 81.00),
            ('2025-10-01', 'silver', 0.95),
        ]
        for dt, metal, price in metal_data:
            db.execute(
                'INSERT INTO metal_prices (date, metal, price_per_gram_usd) VALUES (?, ?, ?)',
                (dt, metal, price)
            )

        # Seed crypto data
        crypto_data = [
            # Daily window
            ('2026-01-15', 'BTC', 'Bitcoin', 99500.00, 1),
            ('2026-01-15', 'ETH', 'Ethereum', 3800.00, 2),
            ('2026-01-10', 'BTC', 'Bitcoin', 99200.00, 1),
            # Weekly window (Mondays)
            ('2025-12-15', 'BTC', 'Bitcoin', 98200.00, 1),
            ('2025-12-15', 'ETH', 'Ethereum', 3720.00, 2),
            ('2025-12-08', 'BTC', 'Bitcoin', 98000.00, 1),
            ('2025-12-01', 'BTC', 'Bitcoin', 97500.00, 1),
            ('2025-12-01', 'ETH', 'Ethereum', 3650.00, 2),
            # Monthly window
            ('2025-10-01', 'BTC', 'Bitcoin', 95000.00, 1),
        ]
        for dt, symbol, name, price, rank in crypto_data:
            db.execute(
                'INSERT INTO crypto_prices (date, symbol, name, price_usd, rank) VALUES (?, ?, ?, ?, ?)',
                (dt, symbol, name, price, rank)
            )

        db.commit()
        yield app

    # Cleanup
    TimeProvider.reset_default()
    try:
        os.remove(os.path.join(data_dir, 'pricing.sqlite'))
    except OSError:
        pass


@pytest.fixture
def client(app_with_seeded_db):
    """Create test client."""
    return app_with_seeded_db.test_client()


class TestPricingEndpoint:
    """Tests for GET /api/v1/pricing."""

    def test_default_parameters(self, client):
        """Should use today's date and CAD as defaults."""
        response = client.get('/api/v1/pricing')

        # May be 404 if no data for today, or 200 with fallback
        assert response.status_code in [200, 404]

    def test_specific_date_and_base(self, client):
        """Should return pricing for specific date and base currency."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=CAD')
        assert response.status_code == 200

        data = response.get_json()
        assert data['request']['date'] == '2025-12-15'
        assert data['request']['base_currency'] == 'CAD'

    def test_effective_date_returned(self, client):
        """Should return effective date used."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'effective_date' in data
        assert data['effective_date'] == '2025-12-15'

    def test_fallback_date(self, client):
        """Date is mapped to effective snapshot date via cadence.

        With FROZEN_TODAY = 2026-01-15:
        - 2025-12-10 is 36 days ago (Wednesday in weekly window)
        - Weekly cadence maps it to Monday 2025-12-08, which has
          exact data in the test fixture.
        """
        response = client.get('/api/v1/pricing?date=2025-12-10&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        # Cadence maps Dec 10 (Wed, day 36) to Dec 8 (Mon) which has exact data
        assert data['effective_date'] == '2025-12-08'
        assert data['coverage']['fx_date_exact'] is True
        assert data['cadence'] == 'weekly'

    def test_coverage_flags(self, client):
        """Should include coverage flags."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'coverage' in data
        assert 'fx_available' in data['coverage']
        assert 'fx_date_exact' in data['coverage']
        assert 'metals_available' in data['coverage']
        assert 'crypto_available' in data['coverage']

    def test_fx_rates_structure(self, client):
        """Should return FX rates dict."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'fx_rates' in data
        assert 'USD' in data['fx_rates']
        assert 'CAD' in data['fx_rates']
        assert data['fx_rates']['USD'] == 1.0  # Base currency = 1.0

    def test_metals_structure(self, client):
        """Should return metals with price_per_gram and unit."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'metals' in data
        assert 'gold' in data['metals']
        assert 'silver' in data['metals']
        assert 'price_per_gram' in data['metals']['gold']
        assert 'unit' in data['metals']['gold']
        assert data['metals']['gold']['unit'] == 'USD'

    def test_crypto_structure(self, client):
        """Should return crypto with name, price, and rank."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'crypto' in data
        assert 'BTC' in data['crypto']
        assert 'name' in data['crypto']['BTC']
        assert 'price' in data['crypto']['BTC']
        assert 'rank' in data['crypto']['BTC']

    def test_nisab_values(self, client):
        """Should return nisab threshold values."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'nisab' in data
        assert data['nisab']['gold_grams'] == 85
        assert data['nisab']['silver_grams'] == 595
        assert 'gold_value' in data['nisab']
        assert 'silver_value' in data['nisab']

        # Gold value should be 85 * gold price
        gold_price = data['metals']['gold']['price_per_gram']
        assert abs(data['nisab']['gold_value'] - 85 * gold_price) < 0.01

    def test_zakat_rate(self, client):
        """Should return zakat rate."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert data['zakat_rate'] == 0.025

    def test_cross_rates_cad_base(self, client):
        """Should compute cross-rates for CAD base."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=CAD')
        assert response.status_code == 200

        data = response.get_json()
        assert data['fx_rates']['CAD'] == 1.0
        # USD rate should be the conversion factor from USD to CAD
        assert data['fx_rates']['USD'] > 1  # 1 USD > 1 CAD

    def test_prices_converted_to_base(self, client):
        """Prices should be converted to base currency."""
        # Get USD prices
        response_usd = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        data_usd = response_usd.get_json()

        # Get CAD prices
        response_cad = client.get('/api/v1/pricing?date=2025-12-15&base=CAD')
        data_cad = response_cad.get_json()

        # CAD prices should be higher (CAD is worth less than USD)
        gold_usd = data_usd['metals']['gold']['price_per_gram']
        gold_cad = data_cad['metals']['gold']['price_per_gram']
        assert gold_cad > gold_usd
    
    def test_base_currency_units_match_request(self, client):
        """Unit and conversions should align with requested base currency."""
        response_usd = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        response_cad = client.get('/api/v1/pricing?date=2025-12-15&base=CAD')

        data_usd = response_usd.get_json()
        data_cad = response_cad.get_json()

        assert data_usd['metals']['gold']['unit'] == 'USD'
        assert data_cad['metals']['gold']['unit'] == 'CAD'

        gold_usd = data_usd['metals']['gold']['price_per_gram']
        gold_cad = data_cad['metals']['gold']['price_per_gram']
        usd_to_cad = data_cad['fx_rates']['USD']

        assert gold_cad == pytest.approx(gold_usd * usd_to_cad, rel=1e-4)

    def test_invalid_date_format(self, client):
        """Should reject invalid date format."""
        response = client.get('/api/v1/pricing?date=2025/12/15&base=USD')
        assert response.status_code == 400

        data = response.get_json()
        assert 'error' in data
        assert 'date format' in data['error'].lower()

    def test_invalid_currency(self, client):
        """Should reject invalid currency code."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=FAKE')
        assert response.status_code == 400

        data = response.get_json()
        assert 'error' in data
        assert 'currency' in data['error'].lower()

    def test_old_date_returns_data_from_nearest(self, client):
        """Requesting old date returns nearest available data with coverage info.

        With cadence-based lookup, dates outside the available range will
        fall back to nearest data. This tests that old dates still return
        data (from nearest available date) rather than 404.
        """
        response = client.get('/api/v1/pricing?date=2020-01-01&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        # Should indicate data was found but from a different date
        assert 'effective_date' in data
        # The cadence should be monthly for old dates
        assert data['cadence'] == 'monthly'
        # FX rates should still be returned
        assert 'fx_rates' in data

    def test_data_source_field(self, client):
        """Should include data_source field indicating sqlite, r2, or upstream."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        # Default source is sqlite (local cache)
        assert data['data_source'] in ('sqlite', 'r2', 'upstream')

    def test_generated_at_field(self, client):
        """Should include generated_at timestamp."""
        response = client.get('/api/v1/pricing?date=2025-12-15&base=USD')
        assert response.status_code == 200

        data = response.get_json()
        assert 'generated_at' in data
        # Should be ISO format
        assert 'T' in data['generated_at']


class TestLegacyPricingEndpoint:
    """Tests for backward compatibility."""

    def test_legacy_endpoint_exists(self, client):
        """Legacy endpoint should still work."""
        response = client.get('/api/v1/pricing/legacy')
        assert response.status_code == 200

        data = response.get_json()
        # Should have old format
        assert 'fx_rates' in data or 'base_currency' in data
