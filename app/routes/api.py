"""API routes for pricing data."""
from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)

# Stub pricing data for MVP
# In production, these would come from real market data APIs
STUB_PRICING = {
    'gold': {
        'price_per_gram_usd': 65.50,
        'nisab_grams': 85,
        'nisab_value_usd': 5567.50,
    },
    'silver': {
        'price_per_gram_usd': 0.82,
        'nisab_grams': 595,
        'nisab_value_usd': 487.90,
    },
    'currency': {
        'base': 'USD',
        'rates': {
            'USD': 1.0,
            'EUR': 0.92,
            'GBP': 0.79,
            'SAR': 3.75,
            'AED': 3.67,
            'MYR': 4.47,
            'PKR': 278.50,
            'INR': 83.12,
        },
    },
    'zakat_rate': 0.025,  # 2.5%
    'last_updated': '2025-01-04T00:00:00Z',
}


@api_bp.route('/pricing')
def get_pricing():
    """Return current pricing data for gold, silver, and currencies."""
    return jsonify(STUB_PRICING)
