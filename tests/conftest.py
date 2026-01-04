"""Pytest fixtures for Zakat Calculator tests."""
import pytest

from app import create_app


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
