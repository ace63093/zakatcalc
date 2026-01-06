"""Tests for /calculate endpoint."""
import pytest

from app.services import cache


@pytest.fixture
def temp_data_dir(monkeypatch, tmp_path):
    """Use temporary directory for cache tests."""
    monkeypatch.setattr(cache, 'DATA_DIR', str(tmp_path))
    return tmp_path


class TestCalculateEndpoint:
    """Tests for POST /api/v1/calculate endpoint."""

    def test_calculate_returns_200(self, client, temp_data_dir):
        """POST /api/v1/calculate returns 200 with valid data."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [{'name': 'Ring', 'weight_grams': 10, 'purity_karat': 22}],
            'cash': [],
            'bank': []
        })
        assert response.status_code == 200

    def test_calculate_returns_result_keys(self, client, temp_data_dir):
        """Response contains required keys."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [],
            'cash': [{'name': 'Wallet', 'amount': 1000, 'currency': 'CAD'}],
            'bank': []
        })
        data = response.get_json()
        
        assert 'master_currency' in data
        assert 'subtotals' in data
        assert 'grand_total' in data
        assert 'nisab_threshold' in data
        assert 'above_nisab' in data
        assert 'zakat_due' in data

    def test_calculate_empty_assets(self, client, temp_data_dir):
        """Empty assets return zero values."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [],
            'cash': [],
            'bank': []
        })
        data = response.get_json()
        
        assert data['grand_total'] == 0.0
        assert data['zakat_due'] == 0.0
        assert data['above_nisab'] is False

    def test_calculate_unsupported_master_currency(self, client, temp_data_dir):
        """Unsupported master currency returns 400."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'EUR',
            'gold': [],
            'cash': [],
            'bank': []
        })
        assert response.status_code == 400
        assert 'error' in response.get_json()

    def test_calculate_invalid_gold_item(self, client, temp_data_dir):
        """Invalid gold item returns 400."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [{'name': 'Ring'}],  # Missing weight_grams and purity_karat
            'cash': [],
            'bank': []
        })
        assert response.status_code == 400

    def test_calculate_invalid_cash_item(self, client, temp_data_dir):
        """Invalid cash item returns 400."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [],
            'cash': [{'name': 'Cash'}],  # Missing amount and currency
            'bank': []
        })
        assert response.status_code == 400

    def test_calculate_unsupported_cash_currency(self, client, temp_data_dir):
        """Unsupported cash currency returns 400."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [],
            'cash': [{'name': 'Cash', 'amount': 100, 'currency': 'EUR'}],
            'bank': []
        })
        assert response.status_code == 400

    def test_calculate_above_nisab(self, client, temp_data_dir):
        """Assets above nisab show zakat due."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [],
            'cash': [],
            'bank': [{'name': 'Savings', 'amount': 50000, 'currency': 'CAD'}]
        })
        data = response.get_json()
        
        assert data['above_nisab'] is True
        assert data['zakat_due'] > 0

    def test_calculate_below_nisab(self, client, temp_data_dir):
        """Assets below nisab show no zakat due."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'CAD',
            'gold': [],
            'cash': [{'name': 'Wallet', 'amount': 100, 'currency': 'CAD'}],
            'bank': []
        })
        data = response.get_json()
        
        assert data['above_nisab'] is False
        assert data['zakat_due'] == 0.0

    def test_calculate_combined_assets(self, client, temp_data_dir):
        """Combined assets calculate correctly."""
        response = client.post('/api/v1/calculate', json={
            'master_currency': 'USD',
            'gold': [{'name': 'Ring', 'weight_grams': 10, 'purity_karat': 24}],
            'cash': [{'name': 'Wallet', 'amount': 500, 'currency': 'USD'}],
            'bank': [{'name': 'Savings', 'amount': 5000, 'currency': 'USD'}]
        })
        data = response.get_json()

        # Gold: 10g * 65 = 650, Cash: 500, Bank: 5000 = 6150 total
        assert data['subtotals']['gold']['total'] > 0
        assert data['subtotals']['cash']['total'] == 500.0
        assert data['subtotals']['bank']['total'] == 5000.0


class TestCalculateV2Endpoint:
    """Tests for POST /api/v1/calculate with new v2 format.

    These tests use db_client which has an initialized pricing database.
    """

    def test_v2_format_detected(self, db_client):
        """New format with base_currency is detected and processed."""
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
        assert 'base_currency' in data

    def test_v2_with_metal_items(self, db_client):
        """New format supports metal_items."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [
                {'name': 'Silver coins', 'metal': 'silver', 'weight_grams': 100}
            ],
            'crypto_items': []
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'subtotals' in data
        assert 'metals' in data['subtotals']
        # 100g * 0.85 USD/g = 85 USD
        assert data['subtotals']['metals']['total'] == 85.0

    def test_v2_with_crypto_items(self, db_client):
        """New format supports crypto_items."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': [
                {'name': 'Bitcoin', 'symbol': 'BTC', 'amount': 0.1}
            ]
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'subtotals' in data
        assert 'crypto' in data['subtotals']
        # 0.1 BTC * 50000 USD = 5000 USD
        assert data['subtotals']['crypto']['total'] == 5000.0

    def test_v2_nisab_structure(self, db_client):
        """V2 format includes detailed nisab information."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        data = response.get_json()

        assert 'nisab' in data
        assert 'gold_grams' in data['nisab']
        assert 'gold_value' in data['nisab']
        assert 'silver_grams' in data['nisab']
        assert 'silver_value' in data['nisab']
        assert 'threshold_used' in data['nisab']

    def test_v2_all_asset_types(self, db_client):
        """V2 format handles all asset types together."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [
                {'name': 'Ring', 'weight_grams': 10, 'purity_karat': 24}
            ],
            'cash_items': [
                {'name': 'Wallet', 'amount': 1000, 'currency': 'USD'}
            ],
            'bank_items': [
                {'name': 'Savings', 'amount': 5000, 'currency': 'USD'}
            ],
            'metal_items': [
                {'name': 'Silver', 'metal': 'silver', 'weight_grams': 100}
            ],
            'crypto_items': [
                {'name': 'BTC', 'symbol': 'BTC', 'amount': 0.01}
            ]
        })
        assert response.status_code == 200
        data = response.get_json()

        assert data['subtotals']['gold']['total'] > 0
        assert data['subtotals']['cash']['total'] == 1000.0
        assert data['subtotals']['bank']['total'] == 5000.0
        assert 'metals' in data['subtotals']
        assert 'crypto' in data['subtotals']

    def test_v2_empty_assets_returns_zeros(self, db_client):
        """Empty v2 request returns zero totals."""
        response = db_client.post('/api/v1/calculate', json={
            'base_currency': 'USD',
            'calculation_date': '2025-01-01',
            'gold_items': [],
            'cash_items': [],
            'bank_items': [],
            'metal_items': [],
            'crypto_items': []
        })
        data = response.get_json()

        assert data['grand_total'] == 0.0
        assert data['zakat_due'] == 0.0
        assert data['above_nisab'] is False
