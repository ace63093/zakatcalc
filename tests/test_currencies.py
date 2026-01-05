"""Tests for currency ordering and the currencies endpoint."""
import pytest
from app import create_app
from app.data.currencies import (
    get_ordered_currencies,
    get_currency_codes,
    is_valid_currency,
    get_currency_info,
    HIGH_VOLUME_CURRENCIES,
    ISO_4217_CURRENCIES,
    DEFAULT_CURRENCY,
)


@pytest.fixture
def app():
    """Create test app."""
    return create_app({'TESTING': True})


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestCurrencyOrdering:
    """Tests for currency ordering logic."""

    def test_cad_is_first(self):
        """CAD must always be first in the list."""
        currencies = get_ordered_currencies()
        assert currencies[0]['code'] == 'CAD'
        assert currencies[0]['priority'] == 1

    def test_high_volume_come_second(self):
        """High-volume currencies should come after CAD."""
        currencies = get_ordered_currencies()
        codes = [c['code'] for c in currencies]

        # Find positions
        cad_pos = codes.index('CAD')
        usd_pos = codes.index('USD')
        eur_pos = codes.index('EUR')

        # CAD is first, USD and EUR come after
        assert cad_pos == 0
        assert usd_pos > cad_pos
        assert eur_pos > cad_pos
        # USD and EUR are high-volume, should be early
        assert usd_pos < 20
        assert eur_pos < 20

    def test_high_volume_order_preserved(self):
        """High-volume currencies should maintain their order."""
        currencies = get_ordered_currencies()
        codes = [c['code'] for c in currencies]

        # Get positions of high-volume currencies that are not CAD
        high_vol_positions = []
        for code in HIGH_VOLUME_CURRENCIES:
            if code in codes and code != 'CAD':
                high_vol_positions.append(codes.index(code))

        # Should be in ascending order (preserving original order)
        assert high_vol_positions == sorted(high_vol_positions)

    def test_remaining_alphabetical(self):
        """Remaining currencies after high-volume should be alphabetical."""
        currencies = get_ordered_currencies()
        priority_3 = [c for c in currencies if c['priority'] == 3]
        codes = [c['code'] for c in priority_3]

        # Should be sorted alphabetically
        assert codes == sorted(codes)

    def test_all_currencies_present(self):
        """All ISO 4217 currencies should be in the list."""
        currencies = get_ordered_currencies()
        codes = {c['code'] for c in currencies}

        assert len(codes) == len(ISO_4217_CURRENCIES)
        for iso_code in ISO_4217_CURRENCIES:
            assert iso_code in codes, f"Missing currency: {iso_code}"

    def test_no_duplicates(self):
        """No currency should appear twice."""
        currencies = get_ordered_currencies()
        codes = [c['code'] for c in currencies]
        assert len(codes) == len(set(codes))

    def test_currency_has_required_fields(self):
        """Each currency should have code, name, minor_unit, priority."""
        currencies = get_ordered_currencies()
        for currency in currencies:
            assert 'code' in currency
            assert 'name' in currency
            assert 'minor_unit' in currency
            assert 'priority' in currency
            assert isinstance(currency['code'], str)
            assert isinstance(currency['name'], str)
            assert isinstance(currency['minor_unit'], int)
            assert currency['priority'] in [1, 2, 3]


class TestCurrencyValidation:
    """Tests for currency validation functions."""

    def test_valid_currencies(self):
        """Valid ISO 4217 codes should be accepted."""
        assert is_valid_currency('CAD') is True
        assert is_valid_currency('USD') is True
        assert is_valid_currency('EUR') is True
        assert is_valid_currency('BDT') is True
        assert is_valid_currency('JPY') is True

    def test_lowercase_valid(self):
        """Lowercase codes should be valid."""
        assert is_valid_currency('cad') is True
        assert is_valid_currency('usd') is True

    def test_invalid_currencies(self):
        """Invalid codes should be rejected."""
        assert is_valid_currency('XYZ') is False
        assert is_valid_currency('FAKE') is False
        assert is_valid_currency('') is False

    def test_get_currency_info(self):
        """get_currency_info should return correct info."""
        info = get_currency_info('CAD')
        assert info is not None
        assert info['code'] == 'CAD'
        assert info['name'] == 'Canadian Dollar'
        assert info['minor_unit'] == 2

    def test_get_currency_info_lowercase(self):
        """get_currency_info should handle lowercase."""
        info = get_currency_info('usd')
        assert info is not None
        assert info['code'] == 'USD'

    def test_get_currency_info_invalid(self):
        """get_currency_info should return None for invalid code."""
        assert get_currency_info('XYZ') is None

    def test_get_currency_codes(self):
        """get_currency_codes should return codes in order."""
        codes = get_currency_codes()
        assert codes[0] == 'CAD'
        assert 'USD' in codes
        assert len(codes) == len(ISO_4217_CURRENCIES)


class TestCurrenciesEndpoint:
    """Tests for the /api/v1/currencies endpoint."""

    def test_returns_currencies(self, client):
        """Endpoint should return currencies list."""
        response = client.get('/api/v1/currencies')
        assert response.status_code == 200

        data = response.get_json()
        assert 'currencies' in data
        assert 'default' in data
        assert 'count' in data

    def test_cad_first(self, client):
        """CAD should be first in the response."""
        response = client.get('/api/v1/currencies')
        data = response.get_json()

        assert data['currencies'][0]['code'] == 'CAD'

    def test_default_is_cad(self, client):
        """Default currency should be CAD."""
        response = client.get('/api/v1/currencies')
        data = response.get_json()

        assert data['default'] == 'CAD'

    def test_count_matches(self, client):
        """Count should match number of currencies."""
        response = client.get('/api/v1/currencies')
        data = response.get_json()

        assert data['count'] == len(data['currencies'])
        assert data['count'] == len(ISO_4217_CURRENCIES)

    def test_priority_ordering_preserved(self, client):
        """Priority ordering should be preserved in response."""
        response = client.get('/api/v1/currencies')
        data = response.get_json()

        currencies = data['currencies']

        # All priority 1 should come before priority 2
        priority_1_indices = [i for i, c in enumerate(currencies) if c['priority'] == 1]
        priority_2_indices = [i for i, c in enumerate(currencies) if c['priority'] == 2]
        priority_3_indices = [i for i, c in enumerate(currencies) if c['priority'] == 3]

        if priority_1_indices and priority_2_indices:
            assert max(priority_1_indices) < min(priority_2_indices)
        if priority_2_indices and priority_3_indices:
            assert max(priority_2_indices) < min(priority_3_indices)

    def test_response_format(self, client):
        """Each currency should have expected fields."""
        response = client.get('/api/v1/currencies')
        data = response.get_json()

        for currency in data['currencies'][:5]:  # Check first 5
            assert 'code' in currency
            assert 'name' in currency
            assert 'minor_unit' in currency
            assert 'priority' in currency
