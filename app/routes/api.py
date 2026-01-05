"""API routes for pricing and calculation."""
from datetime import date, datetime, timezone
from flask import Blueprint, jsonify, request

from app.services.pricing import get_pricing, format_pricing_response
from app.services.calc import calculate_zakat
from app.services.fx import SUPPORTED_CURRENCIES
from app.services.db_pricing import (
    get_fx_snapshot,
    get_metal_snapshot,
    get_crypto_snapshot,
    get_coverage_flags,
    get_available_date_range,
)
from app.data.currencies import (
    get_ordered_currencies,
    is_valid_currency,
    DEFAULT_CURRENCY,
)

api_bp = Blueprint('api', __name__)

NISAB_GOLD_GRAMS = 85
NISAB_SILVER_GRAMS = 595
ZAKAT_RATE = 0.025


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
    """Return pricing snapshot for a specific date and base currency.

    Query Parameters:
        date: YYYY-MM-DD format (default: today)
        base: Base currency code (default: CAD)

    Returns:
        JSON with FX rates, metal prices, crypto prices, and nisab values
        all converted to the base currency. Includes coverage flags indicating
        whether exact date matches were found or fallback dates were used.
    """
    # Parse query parameters
    requested_date = request.args.get('date', date.today().isoformat())
    base_currency = request.args.get('base', DEFAULT_CURRENCY).upper()

    # Validate date format
    try:
        datetime.strptime(requested_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Validate currency
    if not is_valid_currency(base_currency):
        return jsonify({'error': f'Invalid currency: {base_currency}'}), 400

    # Get coverage flags first
    coverage = get_coverage_flags(requested_date)

    # Check if any data is available
    if not coverage['fx_available'] and not coverage['metals_available'] and not coverage['crypto_available']:
        min_date, max_date = get_available_date_range()
        return jsonify({
            'error': 'No pricing data available for requested date range',
            'requested_date': requested_date,
            'earliest_available': min_date,
            'latest_available': max_date,
        }), 404

    # Get pricing snapshots
    fx_effective, fx_rates = get_fx_snapshot(requested_date, base_currency)
    metals_effective, metals = get_metal_snapshot(requested_date, base_currency)
    crypto_effective, crypto = get_crypto_snapshot(requested_date, base_currency)

    # Calculate nisab values in base currency
    gold_price = metals.get('gold', 0)
    silver_price = metals.get('silver', 0)
    nisab_gold_value = round(NISAB_GOLD_GRAMS * gold_price, 2)
    nisab_silver_value = round(NISAB_SILVER_GRAMS * silver_price, 2)

    # Build response
    response = {
        'request': {
            'date': requested_date,
            'base_currency': base_currency,
        },
        'effective_date': fx_effective or metals_effective or crypto_effective,
        'coverage': {
            'fx_available': coverage['fx_available'],
            'fx_date_exact': coverage['fx_date_exact'],
            'metals_available': coverage['metals_available'],
            'metals_date_exact': coverage['metals_date_exact'],
            'crypto_available': coverage['crypto_available'],
            'crypto_date_exact': coverage['crypto_date_exact'],
        },
        'fx_rates': fx_rates,
        'metals': {
            'gold': {'price_per_gram': gold_price, 'unit': base_currency},
            'silver': {'price_per_gram': metals.get('silver', 0), 'unit': base_currency},
            'platinum': {'price_per_gram': metals.get('platinum', 0), 'unit': base_currency},
            'palladium': {'price_per_gram': metals.get('palladium', 0), 'unit': base_currency},
        },
        'crypto': crypto,
        'nisab': {
            'gold_grams': NISAB_GOLD_GRAMS,
            'silver_grams': NISAB_SILVER_GRAMS,
            'gold_value': nisab_gold_value,
            'silver_value': nisab_silver_value,
        },
        'zakat_rate': ZAKAT_RATE,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'data_source': 'local_store',
    }

    return jsonify(response)


@api_bp.route('/pricing/legacy')
def pricing_legacy():
    """Legacy pricing endpoint for backward compatibility."""
    data, status = get_pricing()
    return jsonify(format_pricing_response(data, status))


@api_bp.route('/pricing/refresh', methods=['POST'])
def pricing_refresh():
    """Force refresh pricing data, bypassing cache (legacy)."""
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
