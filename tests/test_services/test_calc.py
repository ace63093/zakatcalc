"""Tests for calc service."""
import pytest

from app.services.calc import (
    karat_to_fraction,
    calculate_pure_grams,
    calculate_gold_subtotal,
    calculate_gold_subtotal_usd,
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
        # Gold price is already in base currency (CAD), not USD
        gold_price_cad = 65.0
        result = calculate_gold_subtotal(items, gold_price_cad, 'CAD', fx_rates)

        assert len(result['items']) == 1
        assert result['items'][0]['pure_grams'] == 10.0
        # 10g * 65 CAD/g = 650 CAD
        assert result['total'] == pytest.approx(650.0, rel=0.01)

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

    def test_usd_price_converts_to_master(self):
        """USD price per gram converts to master currency correctly."""
        price_per_oz_usd = 2000.0
        price_per_gram_usd = price_per_oz_usd / 31.1034768
        items = [{'name': 'Bar', 'weight_grams': 20, 'purity_karat': 24}]
        fx_rates = {'USD': 1.0, 'CAD': 1.5}

        result = calculate_gold_subtotal_usd(items, price_per_gram_usd, 'CAD', fx_rates)

        assert result['total'] == pytest.approx(1929.05, rel=0.001)


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


class TestCalculateMetalSubtotal:
    """Tests for calculate_metal_subtotal function."""

    def test_silver_calculation(self):
        """Silver calculation with price per gram."""
        from app.services.calc import calculate_metal_subtotal

        items = [{'name': 'Silver coins', 'metal': 'silver', 'weight_grams': 100}]
        metal_prices = {'silver': 0.85, 'platinum': 30.0, 'palladium': 35.0}

        result = calculate_metal_subtotal(items, metal_prices, 'USD')

        assert len(result['items']) == 1
        assert result['items'][0]['metal'] == 'silver'
        assert result['items'][0]['weight_grams'] == 100
        assert result['items'][0]['value'] == pytest.approx(85.0, rel=0.01)
        assert result['total'] == pytest.approx(85.0, rel=0.01)

    def test_multiple_metals(self):
        """Multiple metal types sum correctly."""
        from app.services.calc import calculate_metal_subtotal

        items = [
            {'name': 'Silver', 'metal': 'silver', 'weight_grams': 100},
            {'name': 'Platinum', 'metal': 'platinum', 'weight_grams': 10},
        ]
        metal_prices = {'silver': 1.0, 'platinum': 30.0}

        result = calculate_metal_subtotal(items, metal_prices, 'USD')

        # Silver: 100 * 1.0 = 100
        # Platinum: 10 * 30.0 = 300
        assert result['total'] == pytest.approx(400.0, rel=0.01)

    def test_empty_items(self):
        """Empty items returns zero total."""
        from app.services.calc import calculate_metal_subtotal

        result = calculate_metal_subtotal([], {'silver': 1.0}, 'USD')
        assert result['items'] == []
        assert result['total'] == 0.0

    def test_unknown_metal_returns_zero(self):
        """Unknown metal type gets zero price."""
        from app.services.calc import calculate_metal_subtotal

        items = [{'name': 'Unknown', 'metal': 'unobtanium', 'weight_grams': 100}]
        metal_prices = {'silver': 1.0}

        result = calculate_metal_subtotal(items, metal_prices, 'USD')
        assert result['items'][0]['value'] == 0.0
        assert result['total'] == 0.0


class TestCalculateCryptoSubtotal:
    """Tests for calculate_crypto_subtotal function."""

    def test_single_crypto(self):
        """Single crypto calculation."""
        from app.services.calc import calculate_crypto_subtotal

        items = [{'name': 'Bitcoin', 'symbol': 'BTC', 'amount': 0.5}]
        crypto_prices = {'BTC': {'name': 'Bitcoin', 'price': 50000, 'rank': 1}}

        result = calculate_crypto_subtotal(items, crypto_prices, 'USD')

        assert len(result['items']) == 1
        assert result['items'][0]['symbol'] == 'BTC'
        assert result['items'][0]['amount'] == 0.5
        assert result['items'][0]['value'] == pytest.approx(25000.0, rel=0.01)
        assert result['total'] == pytest.approx(25000.0, rel=0.01)

    def test_multiple_cryptos(self):
        """Multiple crypto assets sum correctly."""
        from app.services.calc import calculate_crypto_subtotal

        items = [
            {'name': 'BTC Holdings', 'symbol': 'BTC', 'amount': 1.0},
            {'name': 'ETH Holdings', 'symbol': 'ETH', 'amount': 10.0},
        ]
        crypto_prices = {
            'BTC': {'name': 'Bitcoin', 'price': 50000, 'rank': 1},
            'ETH': {'name': 'Ethereum', 'price': 3000, 'rank': 2},
        }

        result = calculate_crypto_subtotal(items, crypto_prices, 'USD')

        # BTC: 1.0 * 50000 = 50000
        # ETH: 10.0 * 3000 = 30000
        assert result['total'] == pytest.approx(80000.0, rel=0.01)

    def test_empty_items(self):
        """Empty items returns zero total."""
        from app.services.calc import calculate_crypto_subtotal

        result = calculate_crypto_subtotal([], {'BTC': {'price': 50000}}, 'USD')
        assert result['items'] == []
        assert result['total'] == 0.0

    def test_unknown_crypto_returns_zero(self):
        """Unknown crypto symbol gets zero price."""
        from app.services.calc import calculate_crypto_subtotal

        items = [{'name': 'Unknown', 'symbol': 'UNKNOWN', 'amount': 100}]
        crypto_prices = {'BTC': {'price': 50000}}

        result = calculate_crypto_subtotal(items, crypto_prices, 'USD')
        assert result['items'][0]['value'] == 0.0
        assert result['total'] == 0.0

    def test_symbol_case_insensitive(self):
        """Symbols are normalized to uppercase."""
        from app.services.calc import calculate_crypto_subtotal

        items = [{'name': 'Bitcoin', 'symbol': 'btc', 'amount': 1.0}]
        crypto_prices = {'BTC': {'name': 'Bitcoin', 'price': 50000, 'rank': 1}}

        result = calculate_crypto_subtotal(items, crypto_prices, 'USD')
        assert result['items'][0]['symbol'] == 'BTC'
        assert result['total'] == pytest.approx(50000.0, rel=0.01)


class TestCalculateZakatV2:
    """Tests for calculate_zakat_v2 function."""

    def test_all_asset_categories(self):
        """Calculation with all asset categories."""
        from app.services.calc import calculate_zakat_v2

        pricing = {
            'fx_rates': {'USD': 1.0, 'CAD': 0.75},
            'metals': {
                'gold': {'price_per_gram': 65.0},
                'silver': {'price_per_gram': 0.85},
            },
            'crypto': {
                'BTC': {'name': 'Bitcoin', 'price': 50000, 'rank': 1},
            },
        }

        gold = [{'name': 'Ring', 'weight_grams': 10, 'purity_karat': 24}]  # 650
        cash = [{'name': 'Wallet', 'amount': 500, 'currency': 'USD'}]  # 500
        bank = [{'name': 'Savings', 'amount': 1000, 'currency': 'USD'}]  # 1000
        metals = [{'name': 'Silver', 'metal': 'silver', 'weight_grams': 100}]  # 85
        crypto = [{'name': 'BTC', 'symbol': 'BTC', 'amount': 0.01}]  # 500

        result = calculate_zakat_v2(gold, cash, bank, metals, crypto, 'USD', pricing)

        # Total: 650 + 500 + 1000 + 85 + 500 = 2735
        assert result['base_currency'] == 'USD'
        assert result['subtotals']['gold']['total'] == pytest.approx(650.0, rel=0.01)
        assert result['subtotals']['cash']['total'] == pytest.approx(500.0, rel=0.01)
        assert result['subtotals']['bank']['total'] == pytest.approx(1000.0, rel=0.01)
        assert result['subtotals']['metals']['total'] == pytest.approx(85.0, rel=0.01)
        assert result['subtotals']['crypto']['total'] == pytest.approx(500.0, rel=0.01)
        assert result['grand_total'] == pytest.approx(2735.0, rel=0.01)

    def test_nisab_calculation(self):
        """Nisab threshold is calculated correctly."""
        from app.services.calc import calculate_zakat_v2, NISAB_GOLD_GRAMS

        pricing = {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': 65.0},
                'silver': {'price_per_gram': 0.85},
            },
            'crypto': {},
        }

        result = calculate_zakat_v2([], [], [], [], [], 'USD', pricing)

        # Gold nisab: 85 * 65 = 5525
        # Silver nisab: 595 * 0.85 = 505.75
        # Default basis is gold
        assert result['nisab']['gold_threshold'] == pytest.approx(5525.0, rel=0.01)
        assert result['nisab']['silver_threshold'] == pytest.approx(505.75, rel=0.01)
        assert result['nisab']['basis_used'] == 'gold'
        assert result['nisab']['threshold_used'] == pytest.approx(5525.0, rel=0.01)

    def test_above_nisab_with_crypto(self):
        """Above nisab with crypto triggers zakat."""
        from app.services.calc import calculate_zakat_v2, ZAKAT_RATE

        pricing = {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': 65.0},
                'silver': {'price_per_gram': 0.85},
            },
            'crypto': {
                'BTC': {'name': 'Bitcoin', 'price': 50000, 'rank': 1},
            },
        }

        crypto = [{'name': 'BTC', 'symbol': 'BTC', 'amount': 1.0}]  # 50000 USD

        result = calculate_zakat_v2([], [], [], [], crypto, 'USD', pricing)

        assert result['grand_total'] == pytest.approx(50000.0, rel=0.01)
        assert result['above_nisab'] is True
        assert result['zakat_due'] == pytest.approx(50000 * ZAKAT_RATE, rel=0.01)

    def test_below_nisab_no_zakat(self):
        """Below nisab threshold means no zakat due."""
        from app.services.calc import calculate_zakat_v2

        pricing = {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': 65.0},
                'silver': {'price_per_gram': 0.85},
            },
            'crypto': {},
        }

        cash = [{'name': 'Wallet', 'amount': 100, 'currency': 'USD'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing)

        assert result['grand_total'] == pytest.approx(100.0, rel=0.01)
        assert result['above_nisab'] is False
        assert result['zakat_due'] == 0.0


class TestCreditCardSubtotal:
    """Tests for calculate_credit_card_subtotal function."""

    def test_single_credit_card(self):
        """Single credit card calculation."""
        from app.services.calc import calculate_credit_card_subtotal

        items = [{'name': 'Visa', 'amount': 2000, 'currency': 'USD'}]
        fx_rates = {'USD': 1.0, 'CAD': 0.75}

        result = calculate_credit_card_subtotal(items, 'USD', fx_rates)

        assert len(result['items']) == 1
        assert result['items'][0]['converted_amount'] == 2000.0
        assert result['total'] == pytest.approx(2000.0, rel=0.01)

    def test_credit_card_currency_conversion(self):
        """Credit card amount converted to base currency."""
        from app.services.calc import calculate_credit_card_subtotal

        items = [{'name': 'Mastercard', 'amount': 1000, 'currency': 'CAD'}]
        fx_rates = {'USD': 1.0, 'CAD': 0.75}  # 1 CAD = 0.75 USD

        result = calculate_credit_card_subtotal(items, 'USD', fx_rates)

        # 1000 CAD * (1/0.75) = 1333.33 USD
        assert result['total'] == pytest.approx(1333.33, rel=0.01)

    def test_multiple_credit_cards(self):
        """Multiple credit cards sum correctly."""
        from app.services.calc import calculate_credit_card_subtotal

        items = [
            {'name': 'Visa', 'amount': 1000, 'currency': 'USD'},
            {'name': 'Amex', 'amount': 500, 'currency': 'USD'},
        ]
        fx_rates = {'USD': 1.0}

        result = calculate_credit_card_subtotal(items, 'USD', fx_rates)

        assert result['total'] == pytest.approx(1500.0, rel=0.01)


class TestLoanSubtotal:
    """Tests for calculate_loan_subtotal function."""

    def test_monthly_loan_annualization(self):
        """Monthly loan payment annualized correctly."""
        from app.services.calc import calculate_loan_subtotal

        items = [{'name': 'Car Loan', 'payment_amount': 500, 'currency': 'USD', 'frequency': 'monthly'}]
        fx_rates = {'USD': 1.0}

        result = calculate_loan_subtotal(items, 'USD', fx_rates)

        # 500 * 12 = 6000
        assert len(result['items']) == 1
        assert result['items'][0]['multiplier'] == 12
        assert result['items'][0]['annualized_amount'] == 6000.0
        assert result['total'] == pytest.approx(6000.0, rel=0.01)

    def test_biweekly_loan_annualization(self):
        """Bi-weekly loan payment annualized correctly."""
        from app.services.calc import calculate_loan_subtotal

        items = [{'name': 'Mortgage', 'payment_amount': 1000, 'currency': 'USD', 'frequency': 'biweekly'}]
        fx_rates = {'USD': 1.0}

        result = calculate_loan_subtotal(items, 'USD', fx_rates)

        # 1000 * 26 = 26000
        assert result['items'][0]['multiplier'] == 26
        assert result['items'][0]['annualized_amount'] == 26000.0
        assert result['total'] == pytest.approx(26000.0, rel=0.01)

    def test_weekly_loan_annualization(self):
        """Weekly loan payment annualized correctly."""
        from app.services.calc import calculate_loan_subtotal

        items = [{'name': 'Personal Loan', 'payment_amount': 100, 'currency': 'USD', 'frequency': 'weekly'}]
        fx_rates = {'USD': 1.0}

        result = calculate_loan_subtotal(items, 'USD', fx_rates)

        # 100 * 52 = 5200
        assert result['items'][0]['multiplier'] == 52
        assert result['total'] == pytest.approx(5200.0, rel=0.01)

    def test_quarterly_loan_annualization(self):
        """Quarterly loan payment annualized correctly."""
        from app.services.calc import calculate_loan_subtotal

        items = [{'name': 'Quarterly Payment', 'payment_amount': 3000, 'currency': 'USD', 'frequency': 'quarterly'}]
        fx_rates = {'USD': 1.0}

        result = calculate_loan_subtotal(items, 'USD', fx_rates)

        # 3000 * 4 = 12000
        assert result['items'][0]['multiplier'] == 4
        assert result['total'] == pytest.approx(12000.0, rel=0.01)

    def test_loan_currency_conversion(self):
        """Loan amount converted to base currency after annualization."""
        from app.services.calc import calculate_loan_subtotal

        items = [{'name': 'CAD Loan', 'payment_amount': 500, 'currency': 'CAD', 'frequency': 'monthly'}]
        fx_rates = {'USD': 1.0, 'CAD': 0.75}

        result = calculate_loan_subtotal(items, 'USD', fx_rates)

        # 500 CAD * 12 = 6000 CAD annual
        # 6000 CAD * (1/0.75) = 8000 USD
        assert result['items'][0]['annualized_amount'] == 6000.0
        assert result['total'] == pytest.approx(8000.0, rel=0.01)


class TestZakatV2WithDebts:
    """Tests for calculate_zakat_v2 with debt deductions."""

    def _get_base_pricing(self):
        """Return base pricing for tests."""
        return {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': 65.0},
                'silver': {'price_per_gram': 0.85},
            },
            'crypto': {},
        }

    def test_assets_minus_debts_net_total(self):
        """Net total is assets minus debts."""
        from app.services.calc import calculate_zakat_v2

        pricing = self._get_base_pricing()
        cash = [{'name': 'Cash', 'amount': 10000, 'currency': 'USD'}]
        credit_cards = [{'name': 'Visa', 'amount': 2000, 'currency': 'USD'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing,
                                    credit_card_items=credit_cards)

        assert result['assets_total'] == pytest.approx(10000.0, rel=0.01)
        assert result['debts_total'] == pytest.approx(2000.0, rel=0.01)
        assert result['net_total'] == pytest.approx(8000.0, rel=0.01)

    def test_zakat_calculated_on_net_total(self):
        """Zakat is calculated on net_total, not assets_total."""
        from app.services.calc import calculate_zakat_v2, ZAKAT_RATE

        pricing = self._get_base_pricing()
        # Assets: 10000, Debts: 2000, Net: 8000
        # Nisab (gold): 85 * 65 = 5525
        cash = [{'name': 'Cash', 'amount': 10000, 'currency': 'USD'}]
        credit_cards = [{'name': 'Visa', 'amount': 2000, 'currency': 'USD'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing,
                                    credit_card_items=credit_cards)

        assert result['above_nisab'] is True
        # Zakat on 8000 (net), not 10000 (assets)
        assert result['zakat_due'] == pytest.approx(8000 * ZAKAT_RATE, rel=0.01)

    def test_debts_bring_below_nisab(self):
        """Debts can bring net_total below nisab threshold."""
        from app.services.calc import calculate_zakat_v2

        pricing = self._get_base_pricing()
        # Assets: 6000, Debts: 2000, Net: 4000
        # Nisab (gold): 85 * 65 = 5525
        # Net (4000) < Nisab (5525), so no zakat due
        cash = [{'name': 'Cash', 'amount': 6000, 'currency': 'USD'}]
        credit_cards = [{'name': 'Visa', 'amount': 2000, 'currency': 'USD'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing,
                                    credit_card_items=credit_cards)

        assert result['net_total'] == pytest.approx(4000.0, rel=0.01)
        assert result['above_nisab'] is False
        assert result['zakat_due'] == 0.0

    def test_net_total_floored_at_zero(self):
        """Net total cannot go negative (floored at 0)."""
        from app.services.calc import calculate_zakat_v2

        pricing = self._get_base_pricing()
        # Assets: 1000, Debts: 5000, Net should be 0 (not -4000)
        cash = [{'name': 'Cash', 'amount': 1000, 'currency': 'USD'}]
        credit_cards = [{'name': 'Visa', 'amount': 5000, 'currency': 'USD'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing,
                                    credit_card_items=credit_cards)

        assert result['assets_total'] == pytest.approx(1000.0, rel=0.01)
        assert result['debts_total'] == pytest.approx(5000.0, rel=0.01)
        assert result['net_total'] == 0.0  # Floored at 0
        assert result['zakat_due'] == 0.0

    def test_loan_annualization_in_debts(self):
        """Loans are annualized in debt calculation."""
        from app.services.calc import calculate_zakat_v2

        pricing = self._get_base_pricing()
        cash = [{'name': 'Cash', 'amount': 20000, 'currency': 'USD'}]
        loans = [{'name': 'Car Loan', 'payment_amount': 500, 'currency': 'USD', 'frequency': 'monthly'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing,
                                    loan_items=loans)

        # Loan: 500 * 12 = 6000 annualized
        assert result['subtotals']['debts']['loans']['total'] == pytest.approx(6000.0, rel=0.01)
        assert result['debts_total'] == pytest.approx(6000.0, rel=0.01)
        assert result['net_total'] == pytest.approx(14000.0, rel=0.01)

    def test_combined_credit_cards_and_loans(self):
        """Both credit cards and loans deducted."""
        from app.services.calc import calculate_zakat_v2

        pricing = self._get_base_pricing()
        cash = [{'name': 'Cash', 'amount': 30000, 'currency': 'USD'}]
        credit_cards = [{'name': 'Visa', 'amount': 3000, 'currency': 'USD'}]
        loans = [{'name': 'Car Loan', 'payment_amount': 500, 'currency': 'USD', 'frequency': 'monthly'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing,
                                    credit_card_items=credit_cards, loan_items=loans)

        # Credit cards: 3000
        # Loans: 500 * 12 = 6000
        # Total debts: 9000
        # Net: 30000 - 9000 = 21000
        assert result['subtotals']['debts']['credit_cards']['total'] == pytest.approx(3000.0, rel=0.01)
        assert result['subtotals']['debts']['loans']['total'] == pytest.approx(6000.0, rel=0.01)
        assert result['debts_total'] == pytest.approx(9000.0, rel=0.01)
        assert result['net_total'] == pytest.approx(21000.0, rel=0.01)

    def test_backward_compatibility_no_debts(self):
        """No debt items defaults to empty lists (backward compatibility)."""
        from app.services.calc import calculate_zakat_v2

        pricing = self._get_base_pricing()
        cash = [{'name': 'Cash', 'amount': 10000, 'currency': 'USD'}]

        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing)

        assert result['debts_total'] == 0.0
        assert result['net_total'] == result['assets_total']
        assert result['grand_total'] == result['assets_total']
