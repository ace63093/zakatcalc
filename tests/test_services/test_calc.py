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
        # Lower of the two (silver) should be used
        assert result['nisab']['gold_value'] == pytest.approx(5525.0, rel=0.01)
        assert result['nisab']['silver_value'] == pytest.approx(505.75, rel=0.01)
        assert result['nisab']['threshold_used'] == pytest.approx(505.75, rel=0.01)

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
