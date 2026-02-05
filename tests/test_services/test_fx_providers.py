"""Tests for FX provider implementations."""
import json
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from app.services.providers.fx_providers import FawazExchangeAPIProvider
from app.services.providers import ProviderError, NetworkError


class TestFawazExchangeAPIProvider:
    """Tests for the Fawaz Exchange API provider."""

    @pytest.fixture
    def provider(self):
        """Create a Fawaz provider instance."""
        return FawazExchangeAPIProvider()

    def test_provider_name(self, provider):
        """Provider should have correct name."""
        assert provider.name == "fawaz-exchange-api"

    def test_requires_no_api_key(self, provider):
        """Provider should not require an API key."""
        assert provider.requires_api_key is False
        assert provider.is_configured() is True

    def test_get_rates_success(self, provider):
        """Should parse rates from API response."""
        mock_response = json.dumps({
            "usd": {
                "cad": 1.35,
                "eur": 0.92,
                "gbp": 0.79,
                "bdt": 109.5
            }
        }).encode('utf-8')

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=mock_response)

        with patch('urllib.request.urlopen', return_value=mock_urlopen):
            rates = provider.get_rates(date(2026, 1, 15))

        assert len(rates) >= 4  # CAD, EUR, GBP, BDT + USD base

        # Check specific rates
        rate_dict = {r.currency: r.rate_to_usd for r in rates}
        assert rate_dict['CAD'] == 1.35
        assert rate_dict['EUR'] == 0.92
        assert rate_dict['BDT'] == 109.5
        assert rate_dict['USD'] == 1.0  # Base currency always included

        # Check source
        assert all(r.source == "fawaz-exchange-api" for r in rates)

    def test_get_rates_adds_usd_if_missing(self, provider):
        """Should add USD rate if not in response."""
        mock_response = json.dumps({
            "usd": {
                "cad": 1.35,
            }
        }).encode('utf-8')

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=mock_response)

        with patch('urllib.request.urlopen', return_value=mock_urlopen):
            rates = provider.get_rates(date(2026, 1, 15))

        rate_dict = {r.currency: r.rate_to_usd for r in rates}
        assert 'USD' in rate_dict
        assert rate_dict['USD'] == 1.0

    def test_get_rates_skips_invalid_values(self, provider):
        """Should skip non-numeric rate values."""
        mock_response = json.dumps({
            "usd": {
                "cad": 1.35,
                "invalid": "not_a_number",
                "null_val": None,
                "eur": 0.92
            }
        }).encode('utf-8')

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=mock_response)

        with patch('urllib.request.urlopen', return_value=mock_urlopen):
            rates = provider.get_rates(date(2026, 1, 15))

        rate_dict = {r.currency: r.rate_to_usd for r in rates}
        assert 'CAD' in rate_dict
        assert 'EUR' in rate_dict
        assert 'INVALID' not in rate_dict
        assert 'NULL_VAL' not in rate_dict

    def test_get_rates_uses_latest_for_today(self, provider):
        """Should use 'latest' endpoint for today's date."""
        mock_response = json.dumps({
            "usd": {"cad": 1.35}
        }).encode('utf-8')

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=mock_response)

        with patch('urllib.request.urlopen', return_value=mock_urlopen) as mock_open:
            with patch('app.services.providers.fx_providers.datetime') as mock_dt:
                mock_dt.now.return_value.date.return_value = date(2026, 2, 5)
                provider.get_rates(date(2026, 2, 5))

        # First call should contain 'latest' in URL
        call_url = mock_open.call_args[0][0].full_url
        assert 'latest' in call_url

    def test_get_rates_invalid_response_format(self, provider):
        """Should raise ProviderError on invalid response format."""
        mock_response = json.dumps({
            "usd": "not_a_dict"
        }).encode('utf-8')

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=mock_response)

        # Mock all endpoints to return invalid data
        with patch('urllib.request.urlopen', return_value=mock_urlopen):
            with pytest.raises((ProviderError, NetworkError)):
                provider.get_rates(date(2026, 1, 15))

    def test_currency_codes_uppercase(self, provider):
        """Currency codes should be normalized to uppercase."""
        mock_response = json.dumps({
            "usd": {
                "cad": 1.35,
                "eur": 0.92,
            }
        }).encode('utf-8')

        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=mock_response)

        with patch('urllib.request.urlopen', return_value=mock_urlopen):
            rates = provider.get_rates(date(2026, 1, 15))

        for rate in rates:
            assert rate.currency == rate.currency.upper()
