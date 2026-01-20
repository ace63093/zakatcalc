"""Tests for nisab indicator feature."""
import pytest

from app.services.calc import (
    calculate_zakat_v2,
    NISAB_GOLD_GRAMS,
    NISAB_SILVER_GRAMS,
)


class TestNisabBasisCalculation:
    """Tests for nisab basis threshold calculation."""

    def _get_base_pricing(self, gold_price=65.0, silver_price=0.85):
        """Return base pricing structure for tests."""
        return {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': gold_price},
                'silver': {'price_per_gram': silver_price},
            },
            'crypto': {},
        }

    def test_nisab_gold_basis_calculation(self):
        """Gold basis uses 85g threshold."""
        pricing = self._get_base_pricing(gold_price=100.0, silver_price=1.0)
        
        result = calculate_zakat_v2([], [], [], [], [], 'USD', pricing, nisab_basis='gold')
        
        # Gold nisab: 85g * 100 USD/g = 8500 USD
        assert result['nisab']['gold_grams'] == NISAB_GOLD_GRAMS
        assert result['nisab']['gold_grams'] == 85
        assert result['nisab']['gold_threshold'] == pytest.approx(8500.0, rel=0.01)
        assert result['nisab']['threshold_used'] == pytest.approx(8500.0, rel=0.01)
        assert result['nisab']['basis_used'] == 'gold'

    def test_nisab_silver_basis_calculation(self):
        """Silver basis uses 595g threshold."""
        pricing = self._get_base_pricing(gold_price=100.0, silver_price=1.0)
        
        result = calculate_zakat_v2([], [], [], [], [], 'USD', pricing, nisab_basis='silver')
        
        # Silver nisab: 595g * 1.0 USD/g = 595 USD
        assert result['nisab']['silver_grams'] == NISAB_SILVER_GRAMS
        assert result['nisab']['silver_grams'] == 595
        assert result['nisab']['silver_threshold'] == pytest.approx(595.0, rel=0.01)
        assert result['nisab']['threshold_used'] == pytest.approx(595.0, rel=0.01)
        assert result['nisab']['basis_used'] == 'silver'

    def test_nisab_default_basis_is_gold(self):
        """Default is gold when not specified."""
        pricing = self._get_base_pricing(gold_price=100.0, silver_price=1.0)
        
        # Call without nisab_basis parameter
        result = calculate_zakat_v2([], [], [], [], [], 'USD', pricing)
        
        assert result['nisab']['basis_used'] == 'gold'
        # Gold threshold should be used
        assert result['nisab']['threshold_used'] == pytest.approx(8500.0, rel=0.01)


class TestNisabStatus:
    """Tests for nisab status determination."""

    def _get_base_pricing(self):
        """Return base pricing with predictable nisab thresholds."""
        return {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': 100.0},  # Gold nisab = 85 * 100 = 8500
                'silver': {'price_per_gram': 1.0},  # Silver nisab = 595 * 1 = 595
            },
            'crypto': {},
        }

    def test_nisab_status_below(self):
        """Status is 'below' when ratio < 0.90."""
        pricing = self._get_base_pricing()
        # Gold nisab = 8500 USD
        # Give 4000 USD in cash = 4000/8500 = 0.47 ratio (below 0.90)
        cash = [{'name': 'Wallet', 'amount': 4000, 'currency': 'USD'}]
        
        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing, nisab_basis='gold')
        
        assert result['nisab']['status'] == 'below'
        assert result['above_nisab'] is False

    def test_nisab_status_near(self):
        """Status is 'near' when 0.90 <= ratio < 1.00."""
        pricing = self._get_base_pricing()
        # Gold nisab = 8500 USD
        # Give 8000 USD in cash = 8000/8500 = 0.94 ratio (between 0.90 and 1.0)
        cash = [{'name': 'Wallet', 'amount': 8000, 'currency': 'USD'}]
        
        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing, nisab_basis='gold')
        
        assert result['nisab']['status'] == 'near'
        assert result['above_nisab'] is False

    def test_nisab_status_above(self):
        """Status is 'above' when ratio >= 1.00."""
        pricing = self._get_base_pricing()
        # Gold nisab = 8500 USD
        # Give 10000 USD in cash = 10000/8500 = 1.18 ratio (>= 1.0)
        cash = [{'name': 'Wallet', 'amount': 10000, 'currency': 'USD'}]
        
        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing, nisab_basis='gold')
        
        assert result['nisab']['status'] == 'above'
        assert result['above_nisab'] is True


class TestNisabDifferenceText:
    """Tests for nisab difference text formatting."""

    def _get_base_pricing(self):
        """Return base pricing with predictable nisab thresholds."""
        return {
            'fx_rates': {'USD': 1.0},
            'metals': {
                'gold': {'price_per_gram': 100.0},  # Gold nisab = 85 * 100 = 8500
                'silver': {'price_per_gram': 1.0},
            },
            'crypto': {},
        }

    def test_nisab_difference_text_below(self):
        """Shows 'X more to reach nisab' when below threshold."""
        pricing = self._get_base_pricing()
        # Gold nisab = 8500 USD
        # Give 5000 USD in cash, difference = 3500
        cash = [{'name': 'Wallet', 'amount': 5000, 'currency': 'USD'}]
        
        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing, nisab_basis='gold')
        
        assert 'more to reach nisab' in result['nisab']['difference_text']
        assert result['nisab']['difference'] == pytest.approx(3500.0, rel=0.01)
        assert result['nisab']['difference_text'] == '3500.0 more to reach nisab'

    def test_nisab_difference_text_above(self):
        """Shows 'X above nisab' when above threshold."""
        pricing = self._get_base_pricing()
        # Gold nisab = 8500 USD
        # Give 10000 USD in cash, difference = 1500
        cash = [{'name': 'Wallet', 'amount': 10000, 'currency': 'USD'}]
        
        result = calculate_zakat_v2([], cash, [], [], [], 'USD', pricing, nisab_basis='gold')
        
        assert 'above nisab' in result['nisab']['difference_text']
        assert result['nisab']['difference'] == pytest.approx(1500.0, rel=0.01)
        assert result['nisab']['difference_text'] == '1500.0 above nisab'


class TestNisabEndpointIntegration:
    """Integration tests for nisab_basis parameter in /api/v1/calculate endpoint."""

    def test_endpoint_gold_basis(self, db_client):
        """Endpoint respects nisab_basis='gold' parameter."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'nisab_basis': 'gold',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['nisab']['basis_used'] == 'gold'
        # 85g * 65 USD/g = 5525 USD
        assert data['nisab']['threshold_used'] == pytest.approx(5525.0, rel=0.01)

    def test_endpoint_silver_basis(self, db_client):
        """Endpoint respects nisab_basis='silver' parameter."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'nisab_basis': 'silver',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['nisab']['basis_used'] == 'silver'
        # 595g * 0.85 USD/g = 505.75 USD
        assert data['nisab']['threshold_used'] == pytest.approx(505.75, rel=0.01)

    def test_endpoint_default_gold_basis(self, db_client):
        """Endpoint defaults to gold basis when not specified."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['nisab']['basis_used'] == 'gold'

    def test_endpoint_invalid_basis_falls_back_to_gold(self, db_client):
        """Invalid nisab_basis falls back to gold."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'nisab_basis': 'platinum',  # Invalid
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['nisab']['basis_used'] == 'gold'

    def test_endpoint_nisab_status_fields(self, db_client):
        """Endpoint returns all required nisab indicator fields."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [{'name': 'Wallet', 'amount': 1000, 'currency': 'USD'}],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()
        
        nisab = data['nisab']
        assert 'basis_used' in nisab
        assert 'gold_grams' in nisab
        assert 'gold_threshold' in nisab
        assert 'silver_grams' in nisab
        assert 'silver_threshold' in nisab
        assert 'threshold_used' in nisab
        assert 'ratio' in nisab
        assert 'status' in nisab
        assert 'difference' in nisab
        assert 'difference_text' in nisab


class TestDebtEndpointIntegration:
    """Integration tests for debt deductions in /api/v1/calculate endpoint."""

    def test_endpoint_accepts_credit_cards(self, db_client):
        """Endpoint accepts credit_card_items and deducts from net_total."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [{'name': 'Cash', 'amount': 10000, 'currency': 'USD'}],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': [],
            'credit_card_items': [{'name': 'Visa', 'amount': 2000, 'currency': 'USD'}]
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['assets_total'] == pytest.approx(10000.0, rel=0.01)
        assert data['debts_total'] == pytest.approx(2000.0, rel=0.01)
        assert data['net_total'] == pytest.approx(8000.0, rel=0.01)

    def test_endpoint_accepts_loans(self, db_client):
        """Endpoint accepts loan_items with annualization."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [{'name': 'Cash', 'amount': 20000, 'currency': 'USD'}],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': [],
            'loan_items': [{'name': 'Car Loan', 'payment_amount': 500, 'currency': 'USD', 'frequency': 'monthly'}]
        })
        assert response.status_code == 200
        data = response.get_json()

        # Loan: 500 * 12 = 6000 annual
        assert data['subtotals']['debts']['loans']['total'] == pytest.approx(6000.0, rel=0.01)
        assert data['debts_total'] == pytest.approx(6000.0, rel=0.01)
        assert data['net_total'] == pytest.approx(14000.0, rel=0.01)

    def test_endpoint_debts_affect_zakat(self, db_client):
        """Debts reduce net_total and thus zakat due."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [{'name': 'Cash', 'amount': 10000, 'currency': 'USD'}],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': [],
            'credit_card_items': [{'name': 'Visa', 'amount': 2000, 'currency': 'USD'}]
        })
        assert response.status_code == 200
        data = response.get_json()

        # Net total: 8000, which is above nisab (5525)
        # Zakat: 8000 * 0.025 = 200
        assert data['above_nisab'] is True
        assert data['zakat_due'] == pytest.approx(200.0, rel=0.01)

    def test_endpoint_validates_loan_frequency(self, db_client):
        """Invalid loan frequency returns error."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': [],
            'loan_items': [{'name': 'Loan', 'payment_amount': 500, 'currency': 'USD', 'frequency': 'invalid'}]
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid loan frequency' in data['error']

    def test_endpoint_backward_compatible_no_debts(self, db_client):
        """Endpoint works without debt items (backward compatibility)."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [{'name': 'Cash', 'amount': 10000, 'currency': 'USD'}],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['debts_total'] == 0.0
        assert data['net_total'] == data['assets_total']
