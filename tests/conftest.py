"""Pytest fixtures for Zakat Calculator tests."""
import pytest
import os
import tempfile
from datetime import date, timedelta

from app import create_app
from app.db import get_db, get_schema
from app.services.time_provider import TimeProvider


# Fixed "today" for deterministic tests - 2026-01-15 is a Wednesday
FROZEN_TODAY = date(2026, 1, 15)


@pytest.fixture
def app():
    """Create application for testing.

    Yields:
        Flask application configured for testing.
    """
    app = create_app({'TESTING': True})
    yield app


@pytest.fixture
def client(app):
    """Create test client.

    Args:
        app: Flask application fixture.

    Yields:
        Flask test client for making requests.
    """
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_app(tmp_path):
    """Create application with initialized database for testing.

    Yields:
        Flask application with seeded pricing database.
    """
    db_path = tmp_path / 'pricing.sqlite'
    data_dir = str(tmp_path)

    app = create_app({
        'TESTING': True,
        'DATA_DIR': data_dir,
    })

    # Set environment variable for db module
    old_data_dir = os.environ.get('DATA_DIR')
    os.environ['DATA_DIR'] = data_dir

    with app.app_context():
        # Initialize database schema
        db = get_db()
        db.executescript(get_schema())

        # Insert seed data for testing
        db.executemany(
            'INSERT INTO fx_rates (date, currency, rate_to_usd, source) VALUES (?, ?, ?, ?)',
            [
                ('2025-01-01', 'USD', 1.0, 'seed'),
                ('2025-01-01', 'CAD', 0.72, 'seed'),
                ('2025-01-01', 'EUR', 1.10, 'seed'),
            ]
        )
        db.executemany(
            'INSERT INTO metal_prices (date, metal, price_per_gram_usd, source) VALUES (?, ?, ?, ?)',
            [
                ('2025-01-01', 'gold', 65.0, 'seed'),
                ('2025-01-01', 'silver', 0.85, 'seed'),
                ('2025-01-01', 'platinum', 32.0, 'seed'),
                ('2025-01-01', 'palladium', 35.0, 'seed'),
            ]
        )
        db.executemany(
            'INSERT INTO crypto_prices (date, symbol, name, price_usd, rank, source) VALUES (?, ?, ?, ?, ?, ?)',
            [
                ('2025-01-01', 'BTC', 'Bitcoin', 50000.0, 1, 'seed'),
                ('2025-01-01', 'ETH', 'Ethereum', 3000.0, 2, 'seed'),
            ]
        )
        db.commit()

    yield app

    # Restore environment
    if old_data_dir:
        os.environ['DATA_DIR'] = old_data_dir
    elif 'DATA_DIR' in os.environ:
        del os.environ['DATA_DIR']


@pytest.fixture
def db_client(db_app):
    """Create test client with initialized database.

    Yields:
        Flask test client with seeded pricing database.
    """
    with db_app.test_client() as client:
        yield client


@pytest.fixture
def frozen_time():
    """Fixture that freezes time to FROZEN_TODAY (2026-01-15).

    Yields the TimeProvider for use in tests. Automatically resets
    the default TimeProvider after the test completes.
    """
    provider = TimeProvider(frozen_date=FROZEN_TODAY)
    TimeProvider.set_default(provider)
    yield provider
    TimeProvider.reset_default()


@pytest.fixture
def frozen_today():
    """Returns the frozen date value for assertions."""
    return FROZEN_TODAY


@pytest.fixture
def daily_test_dates(frozen_today):
    """5 daily dates within last 30 days of frozen_today."""
    return [
        frozen_today,                          # Today (day 0)
        frozen_today - timedelta(days=7),      # 1 week ago (day 7)
        frozen_today - timedelta(days=14),     # 2 weeks ago (day 14)
        frozen_today - timedelta(days=21),     # 3 weeks ago (day 21)
        frozen_today - timedelta(days=29),     # Last day of daily window (day 29)
    ]


@pytest.fixture
def weekly_test_dates(frozen_today):
    """2 weekly Mondays in days 31-90 range of frozen_today."""
    # Find Mondays in the 31-90 day range
    day_35 = frozen_today - timedelta(days=35)
    day_70 = frozen_today - timedelta(days=70)

    # Get Monday on or before each date
    monday_35 = day_35 - timedelta(days=day_35.weekday())
    monday_70 = day_70 - timedelta(days=day_70.weekday())

    return [monday_35, monday_70]


@pytest.fixture
def monthly_test_dates(frozen_today):
    """2 monthly snapshots older than 90 days from frozen_today."""
    # Dates older than 90 days
    old_date_1 = frozen_today - timedelta(days=120)  # ~4 months ago
    old_date_2 = frozen_today - timedelta(days=180)  # ~6 months ago

    return [
        old_date_1.replace(day=1),  # 1st of month
        old_date_2.replace(day=1),  # 1st of month
    ]
