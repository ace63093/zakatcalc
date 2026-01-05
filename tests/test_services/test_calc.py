"""Tests for calc service."""
import pytest

from app.services.calc import (
    karat_to_fraction,
    calculate_pure_grams,
    calculate_gold_subtotal,
    calculate_cash_subtotal,
    calculate_bank_subtotal,
    calculate_zakat,
    ZAKAT_RATE,
    NISAB_GOLD_GRAMS,
)


class TestKaratToFraction:
    """Tests for karat_to_fraction function."""

    def test_24k_is_pure(self):
        """24 karat is 100% pure."""
        assert karat_to_fraction(24) == 1.0

    def test_18k_is_75_percent(self):
        """18 karat is 75% pure."""
        assert karat_to_fraction(18) == 0.75

    def test_22k_fraction(self):
        """22 karat is 22/24 pure."""
        assert karat_to_fraction(22) == pytest.approx(22/24)


class TestCalculatePureGrams:
    """Tests for calculate_pure_grams function."""

    def test_pure_gold_unchanged(self):
        """24K gold weight equals pure weight."""
        assert calculate_pure_grams(10.0, 24) == 10.0

    def test_18k_reduction(self):
        """18K gold is 75% pure."""
        assert calculate_pure_grams(10.0, 18) == 7.5

    def test_22k_reduction(self):
        """22K gold reduction."""
        assert calculate_pure_grams(24.0, 22) == pytest.approx(22.0)


class TestCalculateGoldSubtotal:
    """Tests for calculate_gold_subtotal function."""

    def test_single_item(self):
        """Single gold item calculation."""
        items = [{'name': 'Ring', 'weight_grams': 10, 'purity_karat': 24}]
        fx_rates = {'USD': 1.0, 'CAD': 1.38}
        result = calculate_gold_subtotal(items, 65.0, 'CAD', fx_rates)
        
        assert len(result['items']) == 1
        assert result['items'][0]['pure_grams'] == 10.0
        # 10g * 65 USD/g * 1.38 = 897 CAD
        assert result['total'] == pytest.approx(897.0, rel=0.01)

    def test_multiple_items(self):
        """Multiple gold items sum correctly."""
        items = [
            {'name': 'Ring', 'weight_grams': 10, 'purity_karat': 24},
            {'name': 'Chain', 'weight_grams': 20, 'purity_karat': 18},
        ]
        fx_rates = {'USD': 1.0}
        result = calculate_gold_subtotal(items, 65.0, 'USD', fx_rates)
        
        # Ring: 10g * 65 = 650
        # Chain: 20g * 0.75 * 65 = 975
        assert result['total'] == pytest.approx(1625.0, rel=0.01)

    def test_empty_items(self):
        """Empty items list returns zero total."""
        result = calculate_gold_subtotal([], 65.0, 'CAD', {'CAD': 1.38})
        assert result['items'] == []
        assert result['total'] == 0.0


class TestCalculateCashSubtotal:
    """Tests for calculate_cash_subtotal function."""

    def test_same_currency(self):
        """Cash in master currency unchanged."""
        items = [{'name': 'Wallet', 'amount': 500, 'currency': 'CAD'}]
        fx_rates = {'CAD': 1.38, 'USD': 1.0}
        result = calculate_cash_subtotal(items, 'CAD', fx_rates)
        
        assert result['total'] == 500.0
        assert result['items'][0]['fx_rate'] == 1.0

    def test_currency_conversion(self):
        """Cash converted to master currency."""
        items = [{'name': 'Cash', 'amount': 100, 'currency': 'USD'}]
        fx_rates = {'CAD': 1.38, 'USD': 1.0}
        result = calculate_cash_subtotal(items, 'CAD', fx_rates)
        
        assert result['total'] == pytest.approx(138.0, rel=0.01)


class TestCalculateBankSubtotal:
    """Tests for calculate_bank_subtotal function."""

    def test_bank_conversion(self):
        """Bank accounts converted correctly."""
        items = [{'name': 'Savings', 'amount': 10000, 'currency': 'CAD'}]
        fx_rates = {'CAD': 1.38, 'USD': 1.0}
        result = calculate_bank_subtotal(items, 'CAD', fx_rates)
        
        assert result['total'] == 10000.0


class TestCalculateZakat:
    """Tests for calculate_zakat function."""

    def test_above_nisab(self):
        """Zakat due when above nisab."""
        pricing = {
            'fx_rates': {'USD': 1.0, 'CAD': 1.38},
            'metals': {'gold': {'price_per_gram_usd': 65.0}},
            'as_of': '2025-01-01T00:00:00Z',
            'base_currency': 'USD'
        }
        # Nisab: 85g * 65 = 5525 USD = 7624.5 CAD
        # Give 10000 CAD in bank (above nisab)
        gold = []
        cash = []
        bank = [{'name': 'Savings', 'amount': 10000, 'currency': 'CAD'}]
        
        result = calculate_zakat(gold, cash, bank, 'CAD', pricing)
        
        assert result['above_nisab'] is True
        assert result['zakat_due'] == pytest.approx(10000 * 0.025, rel=0.01)
        assert result['master_currency'] == 'CAD'

    def test_below_nisab(self):
        """No zakat due when below nisab."""
        pricing = {
            'fx_rates': {'USD': 1.0, 'CAD': 1.38},
            'metals': {'gold': {'price_per_gram_usd': 65.0}},
            'as_of': '2025-01-01T00:00:00Z',
            'base_currency': 'USD'
        }
        # Nisab: 85g * 65 = 5525 USD = 7624.5 CAD
        # Give 1000 CAD (below nisab)
        bank = [{'name': 'Savings', 'amount': 1000, 'currency': 'CAD'}]
        
        result = calculate_zakat([], [], bank, 'CAD', pricing)
        
        assert result['above_nisab'] is False
        assert result['zakat_due'] == 0.0

    def test_combined_assets(self):
        """Combined gold, cash, bank calculation."""
        pricing = {
            'fx_rates': {'USD': 1.0},
            'metals': {'gold': {'price_per_gram_usd': 65.0}},
            'as_of': '2025-01-01T00:00:00Z',
            'base_currency': 'USD'
        }
        gold = [{'name': 'Ring', 'weight_grams': 10, 'purity_karat': 24}]  # 650 USD
        cash = [{'name': 'Cash', 'amount': 350, 'currency': 'USD'}]  # 350 USD
        bank = [{'name': 'Bank', 'amount': 5000, 'currency': 'USD'}]  # 5000 USD
        
        result = calculate_zakat(gold, cash, bank, 'USD', pricing)
        
        # Total: 650 + 350 + 5000 = 6000 USD
        # Nisab: 85 * 65 = 5525 USD
        assert result['grand_total'] == pytest.approx(6000.0, rel=0.01)
        assert result['above_nisab'] is True
        assert result['zakat_due'] == pytest.approx(6000 * 0.025, rel=0.01)
