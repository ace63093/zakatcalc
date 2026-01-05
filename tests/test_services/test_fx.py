"""Tests for fx service."""
import pytest

from app.services.fx import convert_to_master, validate_currency, SUPPORTED_CURRENCIES


class TestConvertToMaster:
    """Tests for convert_to_master function."""

    def test_same_currency_returns_unchanged(self):
        """Converting same currency returns original amount with rate 1.0."""
        fx_rates = {'CAD': 1.38, 'USD': 1.0}
        amount, rate = convert_to_master(100.0, 'CAD', 'CAD', fx_rates)
        assert amount == 100.0
        assert rate == 1.0

    def test_usd_to_cad_conversion(self):
        """Converting USD to CAD uses correct formula."""
        fx_rates = {'USD': 1.0, 'CAD': 1.38}
        amount, rate = convert_to_master(100.0, 'USD', 'CAD', fx_rates)
        assert rate == 1.38
        assert amount == 138.0

    def test_cad_to_usd_conversion(self):
        """Converting CAD to USD uses correct formula."""
        fx_rates = {'USD': 1.0, 'CAD': 1.38}
        amount, rate = convert_to_master(138.0, 'CAD', 'USD', fx_rates)
        assert rate == pytest.approx(1.0 / 1.38)
        assert amount == pytest.approx(100.0)

    def test_bdt_to_cad_conversion(self):
        """Converting BDT to CAD uses correct formula."""
        fx_rates = {'USD': 1.0, 'CAD': 1.38, 'BDT': 110.0}
        amount, rate = convert_to_master(1100.0, 'BDT', 'CAD', fx_rates)
        expected_rate = 1.38 / 110.0
        assert rate == pytest.approx(expected_rate)
        assert amount == pytest.approx(1100.0 * expected_rate)

    def test_unknown_currency_uses_default(self):
        """Unknown currencies default to rate 1.0."""
        fx_rates = {'USD': 1.0}
        amount, rate = convert_to_master(100.0, 'XYZ', 'USD', fx_rates)
        assert rate == 1.0
        assert amount == 100.0


class TestValidateCurrency:
    """Tests for validate_currency function."""

    def test_supported_currencies_valid(self):
        """All supported currencies should validate."""
        for curr in SUPPORTED_CURRENCIES:
            assert validate_currency(curr) is True

    def test_unsupported_currency_invalid(self):
        """Unsupported currencies should not validate."""
        assert validate_currency('EUR') is False
        assert validate_currency('XYZ') is False
        assert validate_currency('') is False
