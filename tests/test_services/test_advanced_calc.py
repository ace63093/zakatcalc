"""Tests for advanced zakat calculation service."""
import pytest
from app.services.advanced_calc import (
    calculate_stock_subtotal,
    calculate_retirement_subtotal,
    calculate_receivables_subtotal,
    calculate_business_subtotal,
    calculate_property_subtotal,
    calculate_short_term_payables_subtotal,
    calculate_zakat_v3,
)
from app.constants import (
    ZAKATABLE_PORTION_RATE,
    EARLY_WITHDRAWAL_PENALTY_RATE,
)


@pytest.fixture
def fx_rates():
    """Sample FX rates for testing."""
    return {
        'CAD': 1.0,
        'USD': 1.35,
        'EUR': 1.48,
    }


@pytest.fixture
def basic_pricing():
    """Basic pricing fixture for v3 tests."""
    return {
        'fx_rates': {
            'CAD': 1.0,
            'USD': 1.35,
        },
        'metals': {
            'gold': {'price_per_gram': 85.0},
            'silver': {'price_per_gram': 1.05},
        },
        'crypto': {
            'BTC': {'name': 'Bitcoin', 'price': 50000, 'rank': 1},
        },
    }


class TestStockSubtotal:
    """Tests for stock/ETF calculation."""

    def test_market_value_method(self, fx_rates):
        """Market value method includes full value."""
        stocks = [{'name': 'ETF', 'value': 10000, 'currency': 'CAD', 'method': 'market_value'}]
        result = calculate_stock_subtotal(stocks, 'CAD', fx_rates)

        assert result['total'] == 10000
        assert result['items'][0]['method'] == 'market_value'
        assert result['items'][0]['adjusted_value'] == 10000

    def test_zakatable_portion_method(self, fx_rates):
        """Zakatable portion method includes only 30%."""
        stocks = [{'name': 'Stock', 'value': 10000, 'currency': 'CAD', 'method': 'zakatable_portion'}]
        result = calculate_stock_subtotal(stocks, 'CAD', fx_rates)

        expected = 10000 * ZAKATABLE_PORTION_RATE  # 30%
        assert result['total'] == expected
        assert result['items'][0]['adjusted_value'] == expected

    def test_currency_conversion(self, fx_rates):
        """Stock values are converted to base currency."""
        # fx_rates has CAD=1.0, USD=1.35 meaning "1 CAD = 1.35 USD"
        # So 1000 USD / 1.35 = ~740.74 CAD
        stocks = [{'name': 'US Stock', 'value': 1000, 'currency': 'USD', 'method': 'market_value'}]
        result = calculate_stock_subtotal(stocks, 'CAD', fx_rates)

        assert round(result['total'], 2) == 740.74  # 1000 USD / 1.35

    def test_empty_stocks(self, fx_rates):
        """Empty stock list returns zero."""
        result = calculate_stock_subtotal([], 'CAD', fx_rates)
        assert result['total'] == 0
        assert result['items'] == []


class TestRetirementSubtotal:
    """Tests for retirement account calculation."""

    def test_accessible_full_balance(self, fx_rates):
        """Accessible account with full_balance method."""
        accounts = [{'name': 'RRSP', 'balance': 50000, 'currency': 'CAD', 'accessible_now': True, 'method': 'full_balance'}]
        result = calculate_retirement_subtotal(accounts, 'CAD', fx_rates)

        assert result['total'] == 50000

    def test_not_accessible_excluded(self, fx_rates):
        """Non-accessible account with accessible_only method excluded."""
        accounts = [{'name': 'RRSP', 'balance': 50000, 'currency': 'CAD', 'accessible_now': False, 'method': 'accessible_only'}]
        result = calculate_retirement_subtotal(accounts, 'CAD', fx_rates)

        assert result['total'] == 0
        assert result['items'][0]['adjusted_value'] == 0

    def test_penalty_adjusted_method(self, fx_rates):
        """Penalty adjusted method applies 10% reduction."""
        accounts = [{'name': '401k', 'balance': 10000, 'currency': 'CAD', 'accessible_now': True, 'method': 'penalty_adjusted'}]
        result = calculate_retirement_subtotal(accounts, 'CAD', fx_rates)

        expected = 10000 * (1 - EARLY_WITHDRAWAL_PENALTY_RATE)  # 90%
        assert result['total'] == expected


class TestReceivablesSubtotal:
    """Tests for receivables calculation."""

    def test_likely_receivable_included(self, fx_rates):
        """Likely receivables are fully included."""
        receivables = [{'name': 'Client A', 'amount': 5000, 'currency': 'CAD', 'likelihood': 'likely'}]
        result = calculate_receivables_subtotal(receivables, 'CAD', fx_rates)

        assert result['total'] == 5000
        assert result['items'][0]['included'] is True

    def test_uncertain_excluded_by_default(self, fx_rates):
        """Uncertain receivables excluded by default."""
        receivables = [{'name': 'Client B', 'amount': 5000, 'currency': 'CAD', 'likelihood': 'uncertain'}]
        result = calculate_receivables_subtotal(receivables, 'CAD', fx_rates, include_uncertain=False)

        assert result['total'] == 0
        assert result['items'][0]['included'] is False

    def test_uncertain_included_when_enabled(self, fx_rates):
        """Uncertain receivables included at 50% when enabled."""
        receivables = [{'name': 'Client B', 'amount': 5000, 'currency': 'CAD', 'likelihood': 'uncertain'}]
        result = calculate_receivables_subtotal(receivables, 'CAD', fx_rates, include_uncertain=True)

        assert result['total'] == 2500  # 50%
        assert result['items'][0]['included'] is True

    def test_doubtful_always_excluded(self, fx_rates):
        """Doubtful receivables never included."""
        receivables = [{'name': 'Bad Debt', 'amount': 5000, 'currency': 'CAD', 'likelihood': 'doubtful'}]
        result = calculate_receivables_subtotal(receivables, 'CAD', fx_rates, include_uncertain=True)

        assert result['total'] == 0


class TestBusinessSubtotal:
    """Tests for business inventory calculation."""

    def test_business_net_calculation(self, fx_rates):
        """Business assets minus payables."""
        business = {
            'name': 'Shop',
            'resale_value': 20000,
            'business_cash': 5000,
            'receivables': 3000,
            'payables': 8000,
            'currency': 'CAD'
        }
        result = calculate_business_subtotal(business, 'CAD', fx_rates)

        # 20000 + 5000 + 3000 - 8000 = 20000
        assert result['total'] == 20000

    def test_business_floored_at_zero(self, fx_rates):
        """Business value cannot be negative."""
        business = {
            'resale_value': 1000,
            'business_cash': 0,
            'receivables': 0,
            'payables': 5000,
            'currency': 'CAD'
        }
        result = calculate_business_subtotal(business, 'CAD', fx_rates)

        assert result['total'] == 0

    def test_none_business_inventory(self, fx_rates):
        """None business inventory returns zero."""
        result = calculate_business_subtotal(None, 'CAD', fx_rates)
        assert result['total'] == 0


class TestPropertySubtotal:
    """Tests for investment property calculation."""

    def test_resale_intent_includes_market_value(self, fx_rates):
        """Resale intent includes full market value."""
        properties = [{'name': 'Condo', 'intent': 'resale', 'market_value': 300000, 'rental_income': 0, 'currency': 'CAD'}]
        result = calculate_property_subtotal(properties, 'CAD', fx_rates)

        assert result['total'] == 300000

    def test_rental_intent_includes_only_income(self, fx_rates):
        """Rental intent includes only saved rental income."""
        properties = [{'name': 'House', 'intent': 'rental', 'market_value': 500000, 'rental_income': 12000, 'currency': 'CAD'}]
        result = calculate_property_subtotal(properties, 'CAD', fx_rates)

        assert result['total'] == 12000


class TestShortTermPayables:
    """Tests for short-term payables calculation."""

    def test_multiple_payables(self, fx_rates):
        """Multiple payable types summed correctly."""
        payables = [
            {'name': 'Income Tax', 'amount': 5000, 'currency': 'CAD', 'type': 'taxes'},
            {'name': 'Rent', 'amount': 1500, 'currency': 'CAD', 'type': 'rent'},
        ]
        result = calculate_short_term_payables_subtotal(payables, 'CAD', fx_rates)

        assert result['total'] == 6500


class TestCalculateZakatV3:
    """Tests for v3 zakat calculation with advanced assets."""

    def test_basic_assets_only(self, basic_pricing):
        """V3 works with basic assets only (backward compatible)."""
        result = calculate_zakat_v3(
            gold_items=[{'weight_grams': 100, 'purity_karat': 24}],
            cash_items=[],
            bank_items=[],
            metal_items=[],
            crypto_items=[],
            base_currency='CAD',
            pricing=basic_pricing,
        )

        assert result['basic_assets_total'] == 8500  # 100g * 85
        assert result['advanced_assets_total'] == 0
        assert result['assets_total'] == 8500

    def test_with_advanced_assets(self, basic_pricing):
        """V3 includes advanced assets in total."""
        result = calculate_zakat_v3(
            gold_items=[],
            cash_items=[{'amount': 10000, 'currency': 'CAD'}],
            bank_items=[],
            metal_items=[],
            crypto_items=[],
            base_currency='CAD',
            pricing=basic_pricing,
            stock_items=[{'value': 5000, 'currency': 'CAD', 'method': 'market_value'}],
        )

        assert result['basic_assets_total'] == 10000
        assert result['advanced_assets_total'] == 5000
        assert result['assets_total'] == 15000

    def test_debt_policy_in_result(self, basic_pricing):
        """Debt policy is included in result."""
        result = calculate_zakat_v3(
            gold_items=[],
            cash_items=[],
            bank_items=[],
            metal_items=[],
            crypto_items=[],
            base_currency='CAD',
            pricing=basic_pricing,
            debt_policy='total',
        )

        assert result['debt_policy'] == 'total'

    def test_short_term_payables_deducted(self, basic_pricing):
        """Short-term payables are included in debt total."""
        result = calculate_zakat_v3(
            gold_items=[],
            cash_items=[{'amount': 20000, 'currency': 'CAD'}],
            bank_items=[],
            metal_items=[],
            crypto_items=[],
            base_currency='CAD',
            pricing=basic_pricing,
            short_term_payables=[{'amount': 5000, 'currency': 'CAD', 'type': 'taxes'}],
        )

        assert result['assets_total'] == 20000
        assert result['debts_total'] == 5000
        assert result['net_total'] == 15000

    def test_all_subtotals_in_result(self, basic_pricing):
        """All subtotal categories present in result."""
        result = calculate_zakat_v3(
            gold_items=[],
            cash_items=[],
            bank_items=[],
            metal_items=[],
            crypto_items=[],
            base_currency='CAD',
            pricing=basic_pricing,
        )

        # Basic subtotals
        assert 'gold' in result['subtotals']
        assert 'cash' in result['subtotals']
        assert 'bank' in result['subtotals']
        assert 'metals' in result['subtotals']
        assert 'crypto' in result['subtotals']

        # Advanced subtotals
        assert 'stocks' in result['subtotals']
        assert 'retirement' in result['subtotals']
        assert 'receivables' in result['subtotals']
        assert 'business' in result['subtotals']
        assert 'property' in result['subtotals']

        # Debt subtotals
        assert 'credit_cards' in result['subtotals']['debts']
        assert 'loans' in result['subtotals']['debts']
        assert 'short_term_payables' in result['subtotals']['debts']
