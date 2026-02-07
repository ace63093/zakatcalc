"""Tests for Flask app factory behavior."""
from unittest.mock import patch

from app import create_app


@patch('app.services.background_sync.start_background_sync')
def test_create_app_passes_app_to_background_sync(mock_start_background_sync, monkeypatch):
    """When enabled, create_app should pass Flask app into background sync."""
    monkeypatch.setenv('PRICING_BACKGROUND_SYNC', '1')

    app = create_app({'TESTING': True})

    mock_start_background_sync.assert_called_once()
    args, _ = mock_start_background_sync.call_args
    assert len(args) == 1
    assert args[0] is app


@patch('app.services.background_sync.start_background_sync')
def test_create_app_skips_background_sync_when_disabled(mock_start_background_sync, monkeypatch):
    """When disabled, create_app should not start background sync thread."""
    monkeypatch.delenv('PRICING_BACKGROUND_SYNC', raising=False)

    create_app({'TESTING': True})

    mock_start_background_sync.assert_not_called()
