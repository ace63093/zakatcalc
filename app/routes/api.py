"""API routes for pricing and calculation."""
from datetime import date, datetime, timezone
from flask import Blueprint, jsonify, request

from app.services.pricing import get_pricing, format_pricing_response
from app.services.calc import calculate_zakat, calculate_zakat_v2
from app.services.fx import SUPPORTED_CURRENCIES
from app.data.metals import is_valid_metal
from app.data.crypto import is_valid_crypto
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

    Accepts both legacy format (master_currency, gold, cash, bank) and
    new format (base_currency, calculation_date, gold_items, etc.).

    New format JSON body:
    {
        "base_currency": "CAD",
        "calculation_date": "2026-01-05",
        "gold_items": [{"name": "Ring", "weight_grams": 10, "purity_karat": 22}],
        "cash_items": [{"name": "Wallet", "amount": 500, "currency": "CAD"}],
        "bank_items": [{"name": "Savings", "amount": 10000, "currency": "USD"}],
        "metal_items": [{"name": "Silver Coins", "metal": "silver", "weight_grams": 500}],
        "crypto_items": [{"name": "BTC Holdings", "symbol": "BTC", "amount": 0.5}]
    }

    Legacy format (still supported):
    {
        "master_currency": "CAD",
        "gold": [...],
        "cash": [...],
        "bank": [...]
    }
    """
    body = request.get_json() or {}

    # Detect format: new format uses base_currency or calculation_date
    is_new_format = 'base_currency' in body or 'calculation_date' in body or \
                    'gold_items' in body or 'metal_items' in body or 'crypto_items' in body

    if is_new_format:
        return _calculate_v2(body)
    else:
        return _calculate_legacy(body)


def _calculate_legacy(body: dict):
    """Handle legacy calculate request format."""
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


def _calculate_v2(body: dict):
    """Handle new calculate request format with all asset categories."""
    # Parse and validate base_currency
    base_currency = body.get('base_currency', DEFAULT_CURRENCY).upper()
    if not is_valid_currency(base_currency):
        return jsonify({'error': f'Invalid currency: {base_currency}'}), 400

    # Parse and validate calculation_date
    calculation_date = body.get('calculation_date', date.today().isoformat())
    try:
        datetime.strptime(calculation_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Get items (support both new and legacy field names)
    gold_items = body.get('gold_items', body.get('gold', []))
    cash_items = body.get('cash_items', body.get('cash', []))
    bank_items = body.get('bank_items', body.get('bank', []))
    metal_items = body.get('metal_items', [])
    crypto_items = body.get('crypto_items', [])

    # Validate gold items
    for item in gold_items:
        if 'weight_grams' not in item or 'purity_karat' not in item:
            return jsonify({'error': 'Gold items require weight_grams and purity_karat'}), 400

    # Validate cash items
    for item in cash_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Cash items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400

    # Validate bank items
    for item in bank_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Bank items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400

    # Validate metal items
    for item in metal_items:
        if 'metal' not in item or 'weight_grams' not in item:
            return jsonify({'error': 'Metal items require metal and weight_grams'}), 400
        if not is_valid_metal(item['metal']):
            return jsonify({'error': f"Invalid metal: {item['metal']}"}), 400

    # Validate crypto items
    for item in crypto_items:
        if 'symbol' not in item or 'amount' not in item:
            return jsonify({'error': 'Crypto items require symbol and amount'}), 400
        # Don't strictly validate crypto symbols - allow unknown ones with 0 price

    # Get pricing snapshot for the calculation date
    coverage = get_coverage_flags(calculation_date)

    if not coverage['fx_available'] and not coverage['metals_available']:
        min_date, max_date = get_available_date_range()
        return jsonify({
            'error': 'No pricing data available for calculation date',
            'calculation_date': calculation_date,
            'earliest_available': min_date,
            'latest_available': max_date,
        }), 404

    # Get pricing snapshots
    fx_effective, fx_rates = get_fx_snapshot(calculation_date, base_currency)
    metals_effective, metals = get_metal_snapshot(calculation_date, base_currency)
    crypto_effective, crypto = get_crypto_snapshot(calculation_date, base_currency)

    # Build pricing dict for calculate_zakat_v2
    pricing = {
        'fx_rates': fx_rates,
        'metals': {
            'gold': {'price_per_gram': metals.get('gold', 0)},
            'silver': {'price_per_gram': metals.get('silver', 0)},
            'platinum': {'price_per_gram': metals.get('platinum', 0)},
            'palladium': {'price_per_gram': metals.get('palladium', 0)},
        },
        'crypto': crypto,
    }

    # Calculate zakat
    result = calculate_zakat_v2(
        gold_items=gold_items,
        cash_items=cash_items,
        bank_items=bank_items,
        metal_items=metal_items,
        crypto_items=crypto_items,
        base_currency=base_currency,
        pricing=pricing,
    )

    # Add calculation metadata
    effective_date = fx_effective or metals_effective or crypto_effective
    result['calculation_date'] = calculation_date
    result['effective_date'] = effective_date
    result['pricing_metadata'] = {
        'requested_date': calculation_date,
        'effective_date': effective_date,
        'coverage': {
            'fx_date_exact': coverage['fx_date_exact'],
            'metals_date_exact': coverage['metals_date_exact'],
            'crypto_date_exact': coverage['crypto_date_exact'],
        },
    }

    return jsonify(result)
