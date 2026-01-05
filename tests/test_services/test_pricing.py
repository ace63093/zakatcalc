"""Tests for pricing service."""
import pytest

from app.services import cache
from app.services.pricing import get_pricing, generate_stub_pricing, format_pricing_response


@pytest.fixture
def temp_data_dir(monkeypatch, tmp_path):
    """Use temporary directory for cache tests."""
    monkeypatch.setattr(cache, 'DATA_DIR', str(tmp_path))
    return tmp_path


class TestGenerateStubPricing:
    """Tests for generate_stub_pricing function."""

    def test_returns_required_keys(self):
        """Stub pricing has all required keys."""
        data = generate_stub_pricing()
        assert 'base_currency' in data
        assert 'fx_rates' in data
        assert 'metals' in data
        assert 'zakat_rate' in data
        assert 'as_of' in data

    def test_fx_rates_include_supported_currencies(self):
        """FX rates include all supported currencies."""
        data = generate_stub_pricing()
        assert 'USD' in data['fx_rates']
        assert 'CAD' in data['fx_rates']
        assert 'BDT' in data['fx_rates']

    def test_metals_include_gold_and_silver(self):
        """Metals data includes gold and silver."""
        data = generate_stub_pricing()
        assert 'gold' in data['metals']
        assert 'silver' in data['metals']
        assert 'price_per_gram_usd' in data['metals']['gold']
        assert 'nisab_grams' in data['metals']['gold']


class TestGetPricing:
    """Tests for get_pricing function."""

    def test_returns_tuple(self, temp_data_dir):
        """get_pricing returns tuple of (data, status)."""
        result = get_pricing()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_cache_miss_on_first_call(self, temp_data_dir):
        """First call returns cache miss."""
        data, status = get_pricing()
        assert status == 'miss'

    def test_cache_hit_on_second_call(self, temp_data_dir):
        """Second call returns cache hit."""
        get_pricing()  # First call writes cache
        data, status = get_pricing()
        assert status == 'hit'

    def test_force_refresh_bypasses_cache(self, temp_data_dir):
        """force_refresh=True returns refreshed status."""
        get_pricing()  # Populate cache
        data, status = get_pricing(force_refresh=True)
        assert status == 'refreshed'


class TestFormatPricingResponse:
    """Tests for format_pricing_response function."""

    def test_adds_cache_status(self):
        """Adds cache_status to response."""
        data = {'base_currency': 'USD'}
        result = format_pricing_response(data, 'hit')
        assert result['cache_status'] == 'hit'
        assert result['base_currency'] == 'USD'

    def test_preserves_original_data(self):
        """Original data is preserved."""
        data = {'a': 1, 'b': 2}
        result = format_pricing_response(data, 'miss')
        assert result['a'] == 1
        assert result['b'] == 2
