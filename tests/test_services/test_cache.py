"""Tests for cache service."""
import os
import json
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from app.services import cache


@pytest.fixture
def temp_data_dir(monkeypatch, tmp_path):
    """Use temporary directory for cache tests."""
    monkeypatch.setattr(cache, 'DATA_DIR', str(tmp_path))
    return tmp_path


def test_get_cache_path(temp_data_dir):
    """get_cache_path returns correct path."""
    path = cache.get_cache_path()
    assert path == os.path.join(str(temp_data_dir), 'pricing_cache.json')


def test_read_cache_missing_file(temp_data_dir):
    """read_cache returns None when file does not exist."""
    result = cache.read_cache()
    assert result is None


def test_write_and_read_cache(temp_data_dir):
    """write_cache writes data that read_cache can retrieve."""
    data = {
        'as_of': datetime.now(timezone.utc).isoformat(),
        'value': 123
    }
    cache.write_cache(data)
    result = cache.read_cache()
    assert result is not None
    assert result['value'] == 123


def test_is_cache_valid_fresh():
    """is_cache_valid returns True for fresh cache."""
    data = {'as_of': datetime.now(timezone.utc).isoformat()}
    assert cache.is_cache_valid(data) is True


def test_is_cache_valid_expired():
    """is_cache_valid returns False for expired cache."""
    old_time = datetime.now(timezone.utc) - timedelta(seconds=3700)
    data = {'as_of': old_time.isoformat()}
    assert cache.is_cache_valid(data) is False


def test_is_cache_valid_missing_as_of():
    """is_cache_valid returns False when as_of is missing."""
    data = {'value': 123}
    assert cache.is_cache_valid(data) is False


def test_clear_cache(temp_data_dir):
    """clear_cache removes the cache file."""
    data = {'as_of': datetime.now(timezone.utc).isoformat()}
    cache.write_cache(data)
    assert os.path.exists(cache.get_cache_path())
    cache.clear_cache()
    assert not os.path.exists(cache.get_cache_path())


def test_clear_cache_no_file(temp_data_dir):
    """clear_cache does not error when file does not exist."""
    cache.clear_cache()  # Should not raise
