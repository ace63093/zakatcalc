"""API routes for pricing and calculation."""
from flask import Blueprint, jsonify, request

from app.services.pricing import get_pricing, format_pricing_response
from app.services.calc import calculate_zakat
from app.services.fx import SUPPORTED_CURRENCIES
from app.data.currencies import (
    get_ordered_currencies,
    is_valid_currency,
    DEFAULT_CURRENCY,
)

api_bp = Blueprint('api', __name__)


@api_bp.route('/currencies')
def currencies():
    """Return ordered list of all supported currencies.

    Returns:
        JSON with currencies list in priority order:
        - CAD first (project default)
        - High-volume currencies by trading volume
        - Remaining currencies alphabetically by code
    """
    currency_list = get_ordered_currencies()
    return jsonify({
        'currencies': currency_list,
        'default': DEFAULT_CURRENCY,
        'count': len(currency_list)
    })


@api_bp.route('/pricing')
def pricing():
    """Return current pricing data with cache status."""
    data, status = get_pricing()
    return jsonify(format_pricing_response(data, status))


@api_bp.route('/pricing/refresh', methods=['POST'])
def pricing_refresh():
    """Force refresh pricing data, bypassing cache."""
    data, status = get_pricing(force_refresh=True)
    return jsonify(format_pricing_response(data, status))


@api_bp.route('/calculate', methods=['POST'])
def calculate():
    """Calculate zakat from submitted assets.

    Expected JSON body:
    {
        "master_currency": "CAD",
        "gold": [{"name": "Ring", "weight_grams": 10, "purity_karat": 22}],
        "cash": [{"name": "Wallet", "amount": 500, "currency": "CAD"}],
        "bank": [{"name": "Savings", "amount": 10000, "currency": "CAD"}]
    }
    """
    body = request.get_json() or {}

    master_currency = body.get('master_currency', 'CAD')
    if master_currency not in SUPPORTED_CURRENCIES:
        return jsonify({'error': f'Unsupported currency: {master_currency}'}), 400

    gold_items = body.get('gold', [])
    cash_items = body.get('cash', [])
    bank_items = body.get('bank', [])

    # Validate gold items
    for item in gold_items:
        if 'weight_grams' not in item or 'purity_karat' not in item:
            return jsonify({'error': 'Gold items require weight_grams and purity_karat'}), 400

    # Validate cash items
    for item in cash_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Cash items require amount and currency'}), 400
        if item['currency'] not in SUPPORTED_CURRENCIES:
            return jsonify({'error': f"Unsupported currency: {item['currency']}"}), 400

    # Validate bank items
    for item in bank_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Bank items require amount and currency'}), 400
        if item['currency'] not in SUPPORTED_CURRENCIES:
            return jsonify({'error': f"Unsupported currency: {item['currency']}"}), 400

    # Get current pricing
    pricing_data, _ = get_pricing()

    # Calculate zakat
    result = calculate_zakat(gold_items, cash_items, bank_items, master_currency, pricing_data)

    return jsonify(result)
