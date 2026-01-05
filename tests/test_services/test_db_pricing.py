"""Tests for SQLite-backed pricing data queries."""
import os
import tempfile
import pytest
from app import create_app
from app.db import get_db, init_db
from app.services.db_pricing import (
    get_fx_snapshot,
    get_metal_snapshot,
    get_crypto_snapshot,
    get_available_date_range,
    compute_cross_rates,
    get_coverage_flags,
)


@pytest.fixture
def app_with_db():
    """Create app with temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.sqlite')
    data_dir = os.path.dirname(db_path)

    app = create_app({
        'TESTING': True,
        'DATA_DIR': data_dir,
    })

    # Rename the temp file to match expected name
    os.close(db_fd)
    os.rename(db_path, os.path.join(data_dir, 'pricing.sqlite'))

    with app.app_context():
        init_db()
        yield app

    # Cleanup
    try:
        os.remove(os.path.join(data_dir, 'pricing.sqlite'))
    except OSError:
        pass


@pytest.fixture
def db(app_with_db):
    """Get database connection."""
    with app_with_db.app_context():
        yield get_db()


def seed_fx_data(db):
    """Insert test FX data."""
    data = [
        ('2025-12-01', 'CAD', 1.4052),
        ('2025-12-01', 'EUR', 0.9483),
        ('2025-12-01', 'BDT', 119.50),
        ('2025-12-15', 'CAD', 1.4123),
        ('2025-12-15', 'EUR', 0.9512),
        ('2025-12-15', 'BDT', 119.75),
        ('2026-01-01', 'CAD', 1.4200),
        ('2026-01-01', 'EUR', 0.9550),
        ('2026-01-01', 'BDT', 120.00),
    ]
    for date, currency, rate in data:
        db.execute(
            'INSERT INTO fx_rates (date, currency, rate_to_usd) VALUES (?, ?, ?)',
            (date, currency, rate)
        )
    # Always add USD
    for date in ['2025-12-01', '2025-12-15', '2026-01-01']:
        db.execute(
            'INSERT OR IGNORE INTO fx_rates (date, currency, rate_to_usd) VALUES (?, ?, ?)',
            (date, 'USD', 1.0)
        )
    db.commit()


def seed_metal_data(db):
    """Insert test metal data."""
    data = [
        ('2025-12-01', 'gold', 82.50),
        ('2025-12-01', 'silver', 0.98),
        ('2025-12-01', 'platinum', 31.20),
        ('2025-12-15', 'gold', 83.00),
        ('2025-12-15', 'silver', 1.00),
        ('2026-01-01', 'gold', 84.00),
        ('2026-01-01', 'silver', 1.02),
    ]
    for date, metal, price in data:
        db.execute(
            'INSERT INTO metal_prices (date, metal, price_per_gram_usd) VALUES (?, ?, ?)',
            (date, metal, price)
        )
    db.commit()


def seed_crypto_data(db):
    """Insert test crypto data."""
    data = [
        ('2025-12-01', 'BTC', 'Bitcoin', 97500.00, 1),
        ('2025-12-01', 'ETH', 'Ethereum', 3650.00, 2),
        ('2025-12-15', 'BTC', 'Bitcoin', 98200.00, 1),
        ('2025-12-15', 'ETH', 'Ethereum', 3720.00, 2),
        ('2026-01-01', 'BTC', 'Bitcoin', 99000.00, 1),
        ('2026-01-01', 'ETH', 'Ethereum', 3800.00, 2),
    ]
    for date, symbol, name, price, rank in data:
        db.execute(
            'INSERT INTO crypto_prices (date, symbol, name, price_usd, rank) VALUES (?, ?, ?, ?, ?)',
            (date, symbol, name, price, rank)
        )
    db.commit()


class TestComputeCrossRates:
    """Tests for cross-rate computation."""

    def test_usd_base_returns_original(self):
        """USD base should return rates as-is (inverted for conversion)."""
        usd_rates = {'USD': 1.0, 'CAD': 1.4, 'EUR': 0.95}
        result = compute_cross_rates(usd_rates, 'USD')

        assert result['USD'] == 1.0
        # 1 CAD = 1/1.4 USD = 0.714... USD, so rate = 1.0/1.4
        assert abs(result['CAD'] - 1.0/1.4) < 0.0001
        # 1 EUR = 1/0.95 USD = 1.05... USD, so rate = 1.0/0.95
        assert abs(result['EUR'] - 1.0/0.95) < 0.0001

    def test_cad_base_cross_rates(self):
        """CAD base should compute cross rates correctly."""
        usd_rates = {'USD': 1.0, 'CAD': 1.4, 'EUR': 0.95}
        result = compute_cross_rates(usd_rates, 'CAD')

        assert result['CAD'] == 1.0
        # 1 USD = 1.4 CAD
        assert abs(result['USD'] - 1.4) < 0.0001
        # 1 EUR in CAD: (1/0.95) USD * 1.4 CAD/USD = 1.4/0.95 CAD
        assert abs(result['EUR'] - 1.4/0.95) < 0.0001

    def test_roundtrip_conversion(self):
        """Converting A->B->A should return original amount."""
        usd_rates = {'USD': 1.0, 'CAD': 1.42, 'EUR': 0.955, 'GBP': 0.79}

        # Start with 100 EUR
        amount = 100.0

        # Convert EUR to CAD
        eur_to_cad = compute_cross_rates(usd_rates, 'CAD')
        amount_cad = amount * eur_to_cad['EUR']

        # Convert CAD back to EUR
        cad_to_eur = compute_cross_rates(usd_rates, 'EUR')
        amount_eur = amount_cad * cad_to_eur['CAD']

        assert abs(amount_eur - 100.0) < 0.01

    def test_handles_zero_rate(self):
        """Should handle zero rate gracefully."""
        usd_rates = {'USD': 1.0, 'CAD': 0.0}
        result = compute_cross_rates(usd_rates, 'USD')
        assert result['CAD'] == 0.0


class TestGetFxSnapshot:
    """Tests for FX snapshot retrieval."""

    def test_exact_date_match(self, app_with_db):
        """Should return exact date when available."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)

            effective, rates = get_fx_snapshot('2025-12-15', 'USD')

            assert effective == '2025-12-15'
            assert 'CAD' in rates
            assert 'EUR' in rates
            assert 'USD' in rates

    def test_fallback_to_prior_date(self, app_with_db):
        """Should fall back to most recent prior date."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)

            # Request date between 12-15 and 01-01
            effective, rates = get_fx_snapshot('2025-12-20', 'USD')

            assert effective == '2025-12-15'
            assert 'CAD' in rates

    def test_no_prior_date_returns_empty(self, app_with_db):
        """Should return empty when no prior date exists."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)

            effective, rates = get_fx_snapshot('2020-01-01', 'USD')

            assert effective is None
            assert rates == {}

    def test_cross_rates_with_cad_base(self, app_with_db):
        """Should compute cross rates for CAD base."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)

            effective, rates = get_fx_snapshot('2026-01-01', 'CAD')

            assert effective == '2026-01-01'
            assert rates['CAD'] == 1.0
            # 1 USD = 1.42 CAD
            assert abs(rates['USD'] - 1.42) < 0.01


class TestGetMetalSnapshot:
    """Tests for metal price retrieval."""

    def test_exact_date_match(self, app_with_db):
        """Should return exact date when available."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_metal_data(db)

            effective, metals = get_metal_snapshot('2025-12-15', 'USD')

            assert effective == '2025-12-15'
            assert metals['gold'] == 83.00
            assert metals['silver'] == 1.00

    def test_fallback_to_prior_date(self, app_with_db):
        """Should fall back to most recent prior date."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_metal_data(db)

            effective, metals = get_metal_snapshot('2025-12-10', 'USD')

            assert effective == '2025-12-01'
            assert metals['gold'] == 82.50

    def test_prices_in_different_base(self, app_with_db):
        """Should convert prices to base currency."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_metal_data(db)

            effective, metals = get_metal_snapshot('2026-01-01', 'CAD')

            # Gold: 84 USD * 1.42 CAD/USD = 119.28 CAD
            assert effective == '2026-01-01'
            assert abs(metals['gold'] - 84.0 * 1.42) < 0.1


class TestGetCryptoSnapshot:
    """Tests for crypto price retrieval."""

    def test_exact_date_match(self, app_with_db):
        """Should return exact date when available."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_crypto_data(db)

            effective, crypto = get_crypto_snapshot('2025-12-15', 'USD')

            assert effective == '2025-12-15'
            assert crypto['BTC']['price'] == 98200.00
            assert crypto['BTC']['name'] == 'Bitcoin'
            assert crypto['BTC']['rank'] == 1
            assert crypto['ETH']['price'] == 3720.00

    def test_filter_by_symbols(self, app_with_db):
        """Should filter by specific symbols."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_crypto_data(db)

            effective, crypto = get_crypto_snapshot('2026-01-01', 'USD', symbols=['BTC'])

            assert 'BTC' in crypto
            assert 'ETH' not in crypto

    def test_prices_in_different_base(self, app_with_db):
        """Should convert prices to base currency."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_crypto_data(db)

            effective, crypto = get_crypto_snapshot('2026-01-01', 'CAD')

            # BTC: 99000 USD * 1.42 CAD/USD = 140580 CAD
            assert abs(crypto['BTC']['price'] - 99000 * 1.42) < 1


class TestGetAvailableDateRange:
    """Tests for date range queries."""

    def test_returns_range(self, app_with_db):
        """Should return min and max dates."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_metal_data(db)
            seed_crypto_data(db)

            min_date, max_date = get_available_date_range()

            assert min_date == '2025-12-01'
            assert max_date == '2026-01-01'

    def test_empty_database(self, app_with_db):
        """Should return None for empty database."""
        with app_with_db.app_context():
            min_date, max_date = get_available_date_range()

            assert min_date is None
            assert max_date is None


class TestGetCoverageFlags:
    """Tests for coverage flag queries."""

    def test_all_exact_matches(self, app_with_db):
        """Should indicate exact matches when date exists."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_metal_data(db)
            seed_crypto_data(db)

            flags = get_coverage_flags('2025-12-15')

            assert flags['fx_available'] is True
            assert flags['fx_date_exact'] is True
            assert flags['metals_available'] is True
            assert flags['metals_date_exact'] is True
            assert flags['crypto_available'] is True
            assert flags['crypto_date_exact'] is True

    def test_fallback_dates(self, app_with_db):
        """Should indicate fallback when exact date missing."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)
            seed_metal_data(db)
            seed_crypto_data(db)

            flags = get_coverage_flags('2025-12-20')

            assert flags['fx_available'] is True
            assert flags['fx_date_exact'] is False
            assert flags['fx_effective_date'] == '2025-12-15'

    def test_no_data_available(self, app_with_db):
        """Should indicate unavailable when no prior data."""
        with app_with_db.app_context():
            db = get_db()
            seed_fx_data(db)

            flags = get_coverage_flags('2020-01-01')

            assert flags['fx_available'] is False
            assert flags['fx_date_exact'] is False
