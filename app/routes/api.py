"""API routes for pricing and calculation."""
from datetime import date, datetime, timezone
from flask import Blueprint, jsonify, request, current_app

from app.db import get_db
from app.services.pricing import get_pricing, format_pricing_response
from app.services.calc import calculate_zakat, calculate_zakat_v2
from app.services.advanced_calc import calculate_zakat_v3
from app.services.fx import SUPPORTED_CURRENCIES
from app.services.config import get_feature_flags, is_visitor_logging_enabled
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
from app.services.config import is_sync_enabled, is_auto_sync_enabled
from app.services.sync import get_sync_service
from app.services.providers.registry import get_provider_status
from app.services.cadence import get_effective_snapshot_date, get_cadence_boundaries
from app.services.time_provider import get_today
from app.services.r2_config import is_r2_enabled
from app.services.r2_client import get_r2_client
from app.services.visitor_logging import backup_visitors_to_r2, backfill_visitor_geolocation
from app.constants import (
    NISAB_GOLD_GRAMS,
    NISAB_SILVER_GRAMS,
    ZAKAT_RATE,
    LOAN_FREQUENCY_MULTIPLIERS,
    STOCK_METHODS,
    RETIREMENT_METHODS,
    RECEIVABLE_LIKELIHOODS,
    PROPERTY_INTENTS,
    PAYABLE_TYPES,
    DEBT_POLICIES,
    DEFAULT_DEBT_POLICY,
)

api_bp = Blueprint('api', __name__)

TRACKED_DOMAINS = ('whatismyzakat.com', 'whatismyzakat.ca')


def _domain_rollup(db, domain: str) -> dict:
    """Get unique IP and visit totals for a domain and subdomains."""
    row = db.execute(
        '''
        SELECT
            COUNT(DISTINCT ip_hash) AS unique_ips,
            COALESCE(SUM(visit_count), 0) AS visits,
            MAX(last_seen) AS last_seen
        FROM visitor_domains
        WHERE host = ? OR host LIKE ?
        ''',
        (domain, f'%.{domain}')
    ).fetchone()
    return {
        'unique_ips': int(row['unique_ips'] or 0),
        'visits': int(row['visits'] or 0),
        'last_seen': row['last_seen'],
    }


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
        all converted to the base currency. Includes cadence type (weekly/monthly)
        and coverage flags indicating whether exact date matches were found.
    """
    # Parse query parameters
    today = get_today()
    requested_date_str = request.args.get('date', today.isoformat())
    base_currency = request.args.get('base', DEFAULT_CURRENCY).upper()

    # Validate date format
    try:
        requested_date = datetime.strptime(requested_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Validate currency
    if not is_valid_currency(base_currency):
        return jsonify({'error': f'Invalid currency: {base_currency}'}), 400

    # Calculate effective snapshot date based on cadence
    effective_snapshot_date, cadence = get_effective_snapshot_date(requested_date, today)
    effective_date_str = effective_snapshot_date.isoformat()

    # Check if snapshot exists
    coverage = get_coverage_flags(effective_date_str)
    jit_synced = False
    data_source = 'sqlite'  # Default: data from local SQLite cache

    # JIT sync if snapshot missing and auto-sync enabled
    if not coverage['fx_available'] and is_auto_sync_enabled():
        try:
            current_app.logger.info(f"JIT sync for {effective_date_str} ({cadence})")
            sync_service = get_sync_service()
            sync_service.sync_date(effective_snapshot_date, snapshot_type=cadence)
            coverage = get_coverage_flags(effective_date_str)
            jit_synced = True
            data_source = 'upstream'  # Data was just fetched from provider
        except Exception as e:
            current_app.logger.warning(f"JIT sync failed for {effective_date_str}: {e}")

    # If still no data after JIT sync, try to find any available data
    if not coverage['fx_available'] and not coverage['metals_available']:
        min_date, max_date = get_available_date_range()
        if not min_date:
            return jsonify({
                'error': 'No pricing data available',
                'requested_date': requested_date_str,
                'effective_date': effective_date_str,
                'cadence': cadence,
                'auto_sync_enabled': is_auto_sync_enabled(),
            }), 404

    # Get pricing snapshots using effective date
    fx_effective, fx_rates = get_fx_snapshot(effective_date_str, base_currency)
    metals_effective, metals = get_metal_snapshot(effective_date_str, base_currency)
    crypto_effective, crypto = get_crypto_snapshot(effective_date_str, base_currency)

    # Calculate nisab values in base currency
    gold_price = metals.get('gold', 0)
    silver_price = metals.get('silver', 0)
    nisab_gold_value = round(NISAB_GOLD_GRAMS * gold_price, 2)
    nisab_silver_value = round(NISAB_SILVER_GRAMS * silver_price, 2)

    # Determine actual effective date from data
    actual_effective = fx_effective or metals_effective or crypto_effective or effective_date_str

    # Build auto-sync status
    auto_sync_status = {
        'enabled': is_auto_sync_enabled(),
        'jit_synced': jit_synced,
    }

    # Build response
    response = {
        'request': {
            'date': requested_date_str,
            'base_currency': base_currency,
        },
        'effective_date': actual_effective,
        'cadence': cadence,
        'coverage': {
            'fx_available': coverage['fx_available'],
            'fx_date_exact': coverage['fx_date_exact'],
            'metals_available': coverage['metals_available'],
            'metals_date_exact': coverage['metals_date_exact'],
            'crypto_available': coverage['crypto_available'],
            'crypto_date_exact': coverage['crypto_date_exact'],
        },
        'auto_sync': auto_sync_status,
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
        'data_source': data_source,
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

    Supports three formats:
    - v3 (advanced): Includes stocks, retirement, receivables, business, property
    - v2 (standard): base_currency, calculation_date, gold_items, etc.
    - v1 (legacy): master_currency, gold, cash, bank

    v3 format (advanced assets):
    {
        "base_currency": "CAD",
        "calculation_date": "2026-01-05",
        "gold_items": [...],
        "cash_items": [...],
        "bank_items": [...],
        "metal_items": [...],
        "crypto_items": [...],
        "credit_card_items": [...],
        "loan_items": [...],
        "stock_items": [{"name": "ETF", "value": 10000, "currency": "CAD", "method": "market_value"}],
        "retirement_items": [{"name": "RRSP", "balance": 50000, "currency": "CAD", "accessible_now": true}],
        "receivable_items": [{"name": "Client A", "amount": 5000, "currency": "CAD", "likelihood": "likely"}],
        "business_inventory": {"resale_value": 20000, "business_cash": 5000, ...},
        "investment_property": [{"name": "Condo", "intent": "resale", "market_value": 300000, ...}],
        "short_term_payables": [{"name": "Tax", "amount": 5000, "currency": "CAD", "type": "taxes"}],
        "debt_policy": "12_months"
    }
    """
    body = request.get_json() or {}

    # Detect v3 format: has advanced asset fields
    is_v3_format = any(key in body for key in [
        'stock_items', 'retirement_items', 'receivable_items',
        'business_inventory', 'investment_property', 'short_term_payables',
        'debt_policy', 'advanced_mode'
    ])

    # Detect v2 format: new format with base_currency, etc.
    is_new_format = 'base_currency' in body or 'calculation_date' in body or \
                    'gold_items' in body or 'metal_items' in body or 'crypto_items' in body

    if is_v3_format:
        return _calculate_v3(body)
    elif is_new_format:
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
    calculation_date = body.get('calculation_date', get_today().isoformat())
    try:
        datetime.strptime(calculation_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Parse nisab_basis (gold or silver, default gold)
    nisab_basis = body.get('nisab_basis', 'gold').lower()
    if nisab_basis not in ('gold', 'silver'):
        nisab_basis = 'gold'

    # Get items (support both new and legacy field names)
    gold_items = body.get('gold_items', body.get('gold', []))
    cash_items = body.get('cash_items', body.get('cash', []))
    bank_items = body.get('bank_items', body.get('bank', []))
    metal_items = body.get('metal_items', [])
    crypto_items = body.get('crypto_items', [])
    credit_card_items = body.get('credit_card_items', [])
    loan_items = body.get('loan_items', [])

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

    # Validate credit card items
    for item in credit_card_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Credit card items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400

    # Validate loan items
    valid_frequencies = list(LOAN_FREQUENCY_MULTIPLIERS.keys())
    for item in loan_items:
        if 'payment_amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Loan items require payment_amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        frequency = item.get('frequency', 'monthly')
        if frequency not in valid_frequencies:
            return jsonify({'error': f"Invalid loan frequency: {frequency}. Must be one of: {', '.join(valid_frequencies)}"}), 400

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
        nisab_basis=nisab_basis,
        credit_card_items=credit_card_items,
        loan_items=loan_items,
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


def _calculate_v3(body: dict):
    """Handle v3 calculate request with advanced asset categories.

    This extends v2 with:
    - Stocks/ETFs (with method selection)
    - Retirement accounts (with accessibility toggle)
    - Receivables (with likelihood classification)
    - Business inventory/trade goods
    - Investment property (with intent-based inclusion)
    - Short-term payables (additional debt types)
    - Debt policy selection
    """
    # Check if advanced assets feature is enabled
    feature_flags = get_feature_flags()
    if not feature_flags.get('advanced_assets_enabled', True):
        return jsonify({
            'error': 'Advanced assets feature is disabled',
            'message': 'Set ENABLE_ADVANCED_ASSETS=1 to enable'
        }), 403

    # Parse and validate base_currency
    base_currency = body.get('base_currency', DEFAULT_CURRENCY).upper()
    if not is_valid_currency(base_currency):
        return jsonify({'error': f'Invalid currency: {base_currency}'}), 400

    # Parse and validate calculation_date
    calculation_date = body.get('calculation_date', get_today().isoformat())
    try:
        datetime.strptime(calculation_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Parse nisab_basis
    nisab_basis = body.get('nisab_basis', 'gold').lower()
    if nisab_basis not in ('gold', 'silver'):
        nisab_basis = 'gold'

    # Parse debt_policy
    debt_policy = body.get('debt_policy', DEFAULT_DEBT_POLICY)
    if debt_policy not in DEBT_POLICIES:
        debt_policy = DEFAULT_DEBT_POLICY

    # ==================== BASIC ITEMS ====================
    gold_items = body.get('gold_items', body.get('gold', []))
    cash_items = body.get('cash_items', body.get('cash', []))
    bank_items = body.get('bank_items', body.get('bank', []))
    metal_items = body.get('metal_items', [])
    crypto_items = body.get('crypto_items', [])
    credit_card_items = body.get('credit_card_items', [])
    loan_items = body.get('loan_items', [])

    # ==================== ADVANCED ITEMS ====================
    stock_items = body.get('stock_items', [])
    retirement_items = body.get('retirement_items', [])
    receivable_items = body.get('receivable_items', [])
    business_inventory = body.get('business_inventory')
    investment_property = body.get('investment_property', [])
    short_term_payables = body.get('short_term_payables', [])
    include_uncertain_receivables = body.get('include_uncertain_receivables', False)

    # ==================== VALIDATE BASIC ITEMS ====================
    # (Same validation as v2)
    for item in gold_items:
        if 'weight_grams' not in item or 'purity_karat' not in item:
            return jsonify({'error': 'Gold items require weight_grams and purity_karat'}), 400

    for item in cash_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Cash items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400

    for item in bank_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Bank items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400

    for item in metal_items:
        if 'metal' not in item or 'weight_grams' not in item:
            return jsonify({'error': 'Metal items require metal and weight_grams'}), 400
        if not is_valid_metal(item['metal']):
            return jsonify({'error': f"Invalid metal: {item['metal']}"}), 400

    for item in crypto_items:
        if 'symbol' not in item or 'amount' not in item:
            return jsonify({'error': 'Crypto items require symbol and amount'}), 400

    for item in credit_card_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Credit card items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400

    valid_frequencies = list(LOAN_FREQUENCY_MULTIPLIERS.keys())
    for item in loan_items:
        if 'payment_amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Loan items require payment_amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        frequency = item.get('frequency', 'monthly')
        if frequency not in valid_frequencies:
            return jsonify({'error': f"Invalid loan frequency: {frequency}"}), 400

    # ==================== VALIDATE ADVANCED ITEMS ====================
    # Validate stock items
    valid_stock_methods = list(STOCK_METHODS.keys())
    for item in stock_items:
        if 'value' not in item or 'currency' not in item:
            return jsonify({'error': 'Stock items require value and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        method = item.get('method', 'market_value')
        if method not in valid_stock_methods:
            return jsonify({'error': f"Invalid stock method: {method}"}), 400

    # Validate retirement items
    valid_retirement_methods = list(RETIREMENT_METHODS.keys())
    for item in retirement_items:
        if 'balance' not in item or 'currency' not in item:
            return jsonify({'error': 'Retirement items require balance and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        method = item.get('method', 'accessible_only')
        if method not in valid_retirement_methods:
            return jsonify({'error': f"Invalid retirement method: {method}"}), 400

    # Validate receivable items
    valid_likelihoods = list(RECEIVABLE_LIKELIHOODS.keys())
    for item in receivable_items:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Receivable items require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        likelihood = item.get('likelihood', 'likely')
        if likelihood not in valid_likelihoods:
            return jsonify({'error': f"Invalid receivable likelihood: {likelihood}"}), 400

    # Validate business inventory
    if business_inventory:
        if 'currency' not in business_inventory:
            return jsonify({'error': 'Business inventory requires currency'}), 400
        if not is_valid_currency(business_inventory['currency']):
            return jsonify({'error': f"Invalid currency: {business_inventory['currency']}"}), 400

    # Validate investment property
    valid_intents = list(PROPERTY_INTENTS.keys())
    for item in investment_property:
        if 'currency' not in item:
            return jsonify({'error': 'Investment property items require currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        intent = item.get('intent', 'rental')
        if intent not in valid_intents:
            return jsonify({'error': f"Invalid property intent: {intent}"}), 400

    # Validate short-term payables
    valid_payable_types = list(PAYABLE_TYPES.keys())
    for item in short_term_payables:
        if 'amount' not in item or 'currency' not in item:
            return jsonify({'error': 'Short-term payables require amount and currency'}), 400
        if not is_valid_currency(item['currency']):
            return jsonify({'error': f"Invalid currency: {item['currency']}"}), 400
        payable_type = item.get('type', 'other')
        if payable_type not in valid_payable_types:
            return jsonify({'error': f"Invalid payable type: {payable_type}"}), 400

    # ==================== GET PRICING DATA ====================
    coverage = get_coverage_flags(calculation_date)

    if not coverage['fx_available'] and not coverage['metals_available']:
        min_date, max_date = get_available_date_range()
        return jsonify({
            'error': 'No pricing data available for calculation date',
            'calculation_date': calculation_date,
            'earliest_available': min_date,
            'latest_available': max_date,
        }), 404

    fx_effective, fx_rates = get_fx_snapshot(calculation_date, base_currency)
    metals_effective, metals = get_metal_snapshot(calculation_date, base_currency)
    crypto_effective, crypto = get_crypto_snapshot(calculation_date, base_currency)

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

    # ==================== CALCULATE ZAKAT ====================
    result = calculate_zakat_v3(
        # Basic assets
        gold_items=gold_items,
        cash_items=cash_items,
        bank_items=bank_items,
        metal_items=metal_items,
        crypto_items=crypto_items,
        base_currency=base_currency,
        pricing=pricing,
        nisab_basis=nisab_basis,
        credit_card_items=credit_card_items,
        loan_items=loan_items,
        # Advanced assets
        stock_items=stock_items,
        retirement_items=retirement_items,
        receivable_items=receivable_items,
        business_inventory=business_inventory,
        investment_property=investment_property,
        short_term_payables=short_term_payables,
        # Settings
        debt_policy=debt_policy,
        include_uncertain_receivables=include_uncertain_receivables,
    )

    # Add calculation metadata
    effective_date = fx_effective or metals_effective or crypto_effective
    result['calculation_date'] = calculation_date
    result['effective_date'] = effective_date
    result['api_version'] = 'v3'
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


@api_bp.route('/pricing/sync', methods=['POST'])
def pricing_sync():
    """Sync pricing data for a date range.

    Request body:
    {
        "start_date": "2026-01-01",
        "end_date": "2026-01-05",
        "types": ["fx", "metals", "crypto"]  // optional, defaults to all
    }

    Returns summary of sync results or 403 if sync is disabled.
    """
    if not is_sync_enabled():
        return jsonify({
            'error': 'Network sync disabled',
            'message': 'Set PRICING_ALLOW_NETWORK=1 to enable pricing sync'
        }), 403

    body = request.get_json() or {}

    # Parse dates
    start_str = body.get('start_date')
    end_str = body.get('end_date')

    if not start_str or not end_str:
        return jsonify({'error': 'start_date and end_date are required'}), 400

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if start_date > end_date:
        return jsonify({'error': 'start_date must be before or equal to end_date'}), 400

    types = body.get('types')
    if types and not isinstance(types, list):
        return jsonify({'error': 'types must be a list'}), 400

    # Perform sync
    sync_service = get_sync_service()
    result = sync_service.sync_range(start_date, end_date, types)

    return jsonify(result)


@api_bp.route('/pricing/sync-date', methods=['POST'])
def pricing_sync_date():
    """Sync pricing data for a single date.

    Request body:
    {
        "date": "2026-01-05",
        "types": ["fx", "metals", "crypto"]  // optional, defaults to all
    }

    Used by UI "Download pricing for this date" button.
    """
    if not is_sync_enabled():
        return jsonify({
            'error': 'Network sync disabled',
            'message': 'Set PRICING_ALLOW_NETWORK=1 to enable pricing sync'
        }), 403

    body = request.get_json() or {}

    date_str = body.get('date')
    if not date_str:
        return jsonify({'error': 'date is required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    types = body.get('types')
    if types and not isinstance(types, list):
        return jsonify({'error': 'types must be a list'}), 400

    # Perform sync
    sync_service = get_sync_service()
    result = sync_service.sync_date(target_date, types)

    return jsonify(result)


@api_bp.route('/pricing/sync-status')
def pricing_sync_status():
    """Get sync configuration and data coverage status.

    Returns:
    {
        "sync_enabled": true,
        "auto_sync_enabled": false,
        "r2_enabled": false,
        "providers": {...},
        "data_coverage": {...},
        "cadence": {...},
        "daemon": {...}
    }
    """
    sync_service = get_sync_service()
    daemon_state = sync_service.get_daemon_state()
    last_changes_reported = 0
    if daemon_state and isinstance(daemon_state.get('snapshots_synced'), int):
        last_changes_reported = daemon_state['snapshots_synced']

    return jsonify({
        'sync_enabled': is_sync_enabled(),
        'auto_sync_enabled': is_auto_sync_enabled(),
        'r2_enabled': is_r2_enabled(),
        'last_changes_reported': last_changes_reported,
        'providers': get_provider_status(),
        'data_coverage': sync_service.get_data_coverage(),
        'cadence': get_cadence_boundaries(),
        'daemon': daemon_state,
    })


@api_bp.route('/visitors/sync-now', methods=['POST'])
def visitors_sync_now():
    """Run ad-hoc visitor backup to R2 and return .com/.ca domain stats."""
    if not is_visitor_logging_enabled():
        return jsonify({
            'error': 'Visitor logging disabled',
            'message': 'Set ENABLE_VISITOR_LOGGING=1 to enable visitor logging'
        }), 403

    r2 = get_r2_client()
    if not r2:
        return jsonify({
            'error': 'R2 unavailable',
            'message': 'Set R2_ENABLED=1 with valid R2_* configuration'
        }), 503

    db = get_db()
    geo_backfill = backfill_visitor_geolocation(db)
    backup_visitors_to_r2(db, r2)

    visitors_total = db.execute('SELECT COUNT(*) AS n FROM visitors').fetchone()['n']
    domain_rows_total = db.execute('SELECT COUNT(*) AS n FROM visitor_domains').fetchone()['n']

    domains = {domain: _domain_rollup(db, domain) for domain in TRACKED_DOMAINS}

    return jsonify({
        'success': True,
        'synced_at': datetime.now(timezone.utc).isoformat(),
        'geo_backfill': geo_backfill,
        'totals': {
            'unique_ips': int(visitors_total or 0),
            'domain_rows': int(domain_rows_total or 0),
        },
        'domains': domains,
    })
