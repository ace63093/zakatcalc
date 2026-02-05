"""Advanced zakat calculation service for additional asset types.

This module extends the base calculation with:
- Stocks/ETFs
- Retirement accounts
- Receivables (money owed to you)
- Business inventory/trade goods
- Investment property
- Short-term payables (additional debt types)
"""
from .fx import convert_to_master
from app.constants import (
    NISAB_GOLD_GRAMS,
    NISAB_SILVER_GRAMS,
    ZAKAT_RATE,
    LOAN_FREQUENCY_MULTIPLIERS,
    RECEIVABLE_LIKELIHOODS,
    STOCK_METHODS,
    ZAKATABLE_PORTION_RATE,
    RETIREMENT_METHODS,
    EARLY_WITHDRAWAL_PENALTY_RATE,
    PROPERTY_INTENTS,
    DEFAULT_DEBT_POLICY,
)
from .calc import (
    calculate_gold_subtotal,
    calculate_cash_subtotal,
    calculate_bank_subtotal,
    calculate_metal_subtotal,
    calculate_crypto_subtotal,
    calculate_credit_card_subtotal,
    calculate_loan_subtotal,
)


def calculate_stock_subtotal(stock_items: list, master_currency: str, fx_rates: dict) -> dict:
    """Calculate zakatable value of stocks/ETFs.

    Args:
        stock_items: List of dicts with name, value, currency, method
        master_currency: Target currency for conversion
        fx_rates: FX rate dictionary

    Methods:
        - market_value: Full market value (default, recommended)
        - zakatable_portion: Only 30% (some scholars' opinion for long-term holdings)

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in stock_items:
        value = item.get('value', 0)
        currency = item.get('currency', master_currency)
        method = item.get('method', 'market_value')

        # Apply method adjustment
        if method == 'zakatable_portion':
            adjusted_value = value * ZAKATABLE_PORTION_RATE
        else:
            adjusted_value = value

        # Convert to base currency
        converted, rate = convert_to_master(adjusted_value, currency, master_currency, fx_rates)

        items_out.append({
            'name': item.get('name', 'Stock/ETF'),
            'original_currency': currency,
            'original_value': value,
            'method': method,
            'method_label': STOCK_METHODS.get(method, method),
            'adjusted_value': round(adjusted_value, 2),
            'converted_amount': round(converted, 2),
            'fx_rate': round(rate, 6)
        })
        total += converted

    return {'items': items_out, 'total': round(total, 2)}


def calculate_retirement_subtotal(retirement_items: list, master_currency: str, fx_rates: dict) -> dict:
    """Calculate zakatable value of retirement accounts.

    Args:
        retirement_items: List of dicts with name, balance, currency, accessible_now, method
        master_currency: Target currency for conversion
        fx_rates: FX rate dictionary

    Methods:
        - full_balance: Full account balance (if fully accessible)
        - accessible_only: Only accessible portion (default)
        - penalty_adjusted: After 10% early withdrawal penalty

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in retirement_items:
        balance = item.get('balance', 0)
        currency = item.get('currency', master_currency)
        accessible = item.get('accessible_now', False)
        method = item.get('method', 'accessible_only')

        # Determine zakatable amount based on accessibility and method
        if not accessible and method == 'accessible_only':
            # Not accessible, don't include
            adjusted_value = 0
        elif method == 'penalty_adjusted':
            # Apply early withdrawal penalty
            adjusted_value = balance * (1 - EARLY_WITHDRAWAL_PENALTY_RATE)
        else:
            # Full balance
            adjusted_value = balance

        # Convert to base currency
        converted, rate = convert_to_master(adjusted_value, currency, master_currency, fx_rates)

        items_out.append({
            'name': item.get('name', 'Retirement Account'),
            'original_currency': currency,
            'balance': balance,
            'accessible_now': accessible,
            'method': method,
            'method_label': RETIREMENT_METHODS.get(method, method),
            'adjusted_value': round(adjusted_value, 2),
            'converted_amount': round(converted, 2),
            'fx_rate': round(rate, 6)
        })
        total += converted

    return {'items': items_out, 'total': round(total, 2)}


def calculate_receivables_subtotal(
    receivable_items: list,
    master_currency: str,
    fx_rates: dict,
    include_uncertain: bool = False
) -> dict:
    """Calculate zakatable value of receivables (money owed to you).

    Args:
        receivable_items: List of dicts with name, amount, currency, likelihood
        master_currency: Target currency for conversion
        fx_rates: FX rate dictionary
        include_uncertain: Whether to include uncertain receivables (default: False)

    Likelihoods:
        - likely: Include at 100% (default)
        - uncertain: Include at 50% if include_uncertain=True, else 0%
        - doubtful: Never include (bad debt)

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in receivable_items:
        amount = item.get('amount', 0)
        currency = item.get('currency', master_currency)
        likelihood = item.get('likelihood', 'likely')

        # Get likelihood config
        likelihood_config = RECEIVABLE_LIKELIHOODS.get(likelihood, RECEIVABLE_LIKELIHOODS['likely'])

        # Determine if included
        if likelihood == 'likely':
            include = True
            rate_multiplier = likelihood_config['rate']
        elif likelihood == 'uncertain' and include_uncertain:
            include = True
            rate_multiplier = likelihood_config['rate']
        else:
            include = False
            rate_multiplier = 0

        adjusted_value = amount * rate_multiplier if include else 0

        # Convert to base currency
        converted, fx_rate = convert_to_master(adjusted_value, currency, master_currency, fx_rates)

        items_out.append({
            'name': item.get('name', 'Receivable'),
            'original_currency': currency,
            'amount': amount,
            'likelihood': likelihood,
            'likelihood_label': likelihood_config['label'],
            'included': include,
            'rate_multiplier': rate_multiplier,
            'adjusted_value': round(adjusted_value, 2),
            'converted_amount': round(converted, 2),
            'fx_rate': round(fx_rate, 6)
        })
        total += converted

    return {'items': items_out, 'total': round(total, 2)}


def calculate_business_subtotal(business_inventory: dict, master_currency: str, fx_rates: dict) -> dict:
    """Calculate zakatable value of business assets.

    Business zakat = resale_value + business_cash + receivables - payables

    Args:
        business_inventory: Dict with resale_value, business_cash, receivables, payables, currency
        master_currency: Target currency for conversion
        fx_rates: FX rate dictionary

    Returns:
        Dict with breakdown and total
    """
    if not business_inventory:
        return {'items': [], 'total': 0.0, 'breakdown': None}

    currency = business_inventory.get('currency', master_currency)
    resale_value = business_inventory.get('resale_value', 0)
    business_cash = business_inventory.get('business_cash', 0)
    receivables = business_inventory.get('receivables', 0)
    payables = business_inventory.get('payables', 0)

    # Net business assets (assets minus liabilities)
    net_value = resale_value + business_cash + receivables - payables
    net_value = max(0, net_value)  # Floor at zero

    # Convert to base currency
    converted, rate = convert_to_master(net_value, currency, master_currency, fx_rates)

    breakdown = {
        'original_currency': currency,
        'resale_value': resale_value,
        'business_cash': business_cash,
        'receivables': receivables,
        'payables': payables,
        'net_value': round(net_value, 2),
        'converted_amount': round(converted, 2),
        'fx_rate': round(rate, 6)
    }

    # Create single "item" for consistency
    items_out = [{
        'name': business_inventory.get('name', 'Business Assets'),
        **breakdown
    }]

    return {'items': items_out, 'total': round(converted, 2), 'breakdown': breakdown}


def calculate_property_subtotal(investment_property: list, master_currency: str, fx_rates: dict) -> dict:
    """Calculate zakatable value of investment property.

    Args:
        investment_property: List of dicts with name, intent, market_value, rental_income, currency
        master_currency: Target currency for conversion
        fx_rates: FX rate dictionary

    Intents:
        - resale: Include market value (property held for trading)
        - rental: Include only saved rental income (property held for income)

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in investment_property:
        intent = item.get('intent', 'rental')
        market_value = item.get('market_value', 0)
        rental_income = item.get('rental_income', 0)  # Saved rental income
        currency = item.get('currency', master_currency)

        # Determine zakatable value based on intent
        if intent == 'resale':
            zakatable_value = market_value
        else:
            # Rental intent: only include saved rental income
            zakatable_value = rental_income

        # Convert to base currency
        converted, rate = convert_to_master(zakatable_value, currency, master_currency, fx_rates)

        items_out.append({
            'name': item.get('name', 'Investment Property'),
            'original_currency': currency,
            'intent': intent,
            'intent_label': PROPERTY_INTENTS.get(intent, intent),
            'market_value': market_value,
            'rental_income': rental_income,
            'zakatable_value': round(zakatable_value, 2),
            'converted_amount': round(converted, 2),
            'fx_rate': round(rate, 6)
        })
        total += converted

    return {'items': items_out, 'total': round(total, 2)}


def calculate_short_term_payables_subtotal(payables: list, master_currency: str, fx_rates: dict) -> dict:
    """Calculate deductible short-term payables.

    Args:
        payables: List of dicts with name, amount, currency, type
        master_currency: Target currency for conversion
        fx_rates: FX rate dictionary

    Types:
        - taxes: Taxes owing
        - rent: Rent due
        - utilities: Utilities due
        - other: Other payables

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in payables:
        amount = item.get('amount', 0)
        currency = item.get('currency', master_currency)
        payable_type = item.get('type', 'other')

        # Convert to base currency
        converted, rate = convert_to_master(amount, currency, master_currency, fx_rates)

        items_out.append({
            'name': item.get('name', payable_type.title()),
            'original_currency': currency,
            'amount': amount,
            'type': payable_type,
            'converted_amount': round(converted, 2),
            'fx_rate': round(rate, 6)
        })
        total += converted

    return {'items': items_out, 'total': round(total, 2)}


def apply_debt_policy(loan_total: float, debt_policy: str) -> float:
    """Apply debt policy to loan total.

    Args:
        loan_total: Total annualized loan amount
        debt_policy: '12_months', 'total', or 'custom'

    Returns:
        Adjusted deductible amount
    """
    if debt_policy == '12_months':
        # Default: only deduct next 12 months (loan_total is already annualized)
        return loan_total
    elif debt_policy == 'total':
        # TODO: Would need total outstanding, not implemented yet
        # For now, same as 12_months
        return loan_total
    else:
        # Custom or unknown: use as-is
        return loan_total


def calculate_zakat_v3(
    # Basic assets (same as v2)
    gold_items: list,
    cash_items: list,
    bank_items: list,
    metal_items: list,
    crypto_items: list,
    base_currency: str,
    pricing: dict,
    nisab_basis: str = 'gold',
    credit_card_items: list = None,
    loan_items: list = None,
    # Advanced assets (new in v3)
    stock_items: list = None,
    retirement_items: list = None,
    receivable_items: list = None,
    business_inventory: dict = None,
    investment_property: list = None,
    # Additional debts (new in v3)
    short_term_payables: list = None,
    # Settings (new in v3)
    debt_policy: str = DEFAULT_DEBT_POLICY,
    include_uncertain_receivables: bool = False,
) -> dict:
    """Calculate zakat with all asset categories including advanced assets.

    This is an extended version of calculate_zakat_v2 that supports:
    - Stocks/ETFs with method selection
    - Retirement accounts with accessibility toggle
    - Receivables with likelihood classification
    - Business inventory/trade goods
    - Investment property with intent-based inclusion
    - Short-term payables as additional debts
    - Debt deduction policy selection

    Returns:
        Complete calculation result with all subtotals, debts, net_total, and zakat due
    """
    # Default empty lists for optional parameters
    if credit_card_items is None:
        credit_card_items = []
    if loan_items is None:
        loan_items = []
    if stock_items is None:
        stock_items = []
    if retirement_items is None:
        retirement_items = []
    if receivable_items is None:
        receivable_items = []
    if investment_property is None:
        investment_property = []
    if short_term_payables is None:
        short_term_payables = []

    fx_rates = pricing.get('fx_rates', {})

    # Validate nisab_basis
    if nisab_basis not in ('gold', 'silver'):
        nisab_basis = 'gold'

    # Extract metal prices (already in base currency)
    metals_data = pricing.get('metals', {})
    metal_prices = {}
    for metal_name, metal_info in metals_data.items():
        if isinstance(metal_info, dict):
            metal_prices[metal_name] = metal_info.get('price_per_gram', 0)
        else:
            metal_prices[metal_name] = metal_info

    # Extract crypto prices (already in base currency)
    crypto_prices = pricing.get('crypto', {})

    # Get gold price for gold calculation
    FALLBACK_GOLD_PRICE = 85.0
    FALLBACK_SILVER_PRICE = 1.05

    gold_price = metal_prices.get('gold', 0) or FALLBACK_GOLD_PRICE
    silver_price = metal_prices.get('silver', 0) or FALLBACK_SILVER_PRICE

    # ==================== BASIC ASSET SUBTOTALS ====================
    gold_sub = calculate_gold_subtotal(gold_items, gold_price, base_currency, fx_rates)
    cash_sub = calculate_cash_subtotal(cash_items, base_currency, fx_rates)
    bank_sub = calculate_bank_subtotal(bank_items, base_currency, fx_rates)
    metal_sub = calculate_metal_subtotal(metal_items, metal_prices, base_currency)
    crypto_sub = calculate_crypto_subtotal(crypto_items, crypto_prices, base_currency)

    # ==================== ADVANCED ASSET SUBTOTALS ====================
    stock_sub = calculate_stock_subtotal(stock_items, base_currency, fx_rates)
    retirement_sub = calculate_retirement_subtotal(retirement_items, base_currency, fx_rates)
    receivable_sub = calculate_receivables_subtotal(
        receivable_items, base_currency, fx_rates, include_uncertain_receivables
    )
    business_sub = calculate_business_subtotal(business_inventory, base_currency, fx_rates)
    property_sub = calculate_property_subtotal(investment_property, base_currency, fx_rates)

    # ==================== DEBT SUBTOTALS ====================
    credit_card_sub = calculate_credit_card_subtotal(credit_card_items, base_currency, fx_rates)
    loan_sub = calculate_loan_subtotal(loan_items, base_currency, fx_rates)
    payables_sub = calculate_short_term_payables_subtotal(short_term_payables, base_currency, fx_rates)

    # Apply debt policy to loans
    adjusted_loan_total = apply_debt_policy(loan_sub['total'], debt_policy)

    # ==================== TOTALS ====================
    # Basic assets total
    basic_assets_total = (
        gold_sub['total'] +
        cash_sub['total'] +
        bank_sub['total'] +
        metal_sub['total'] +
        crypto_sub['total']
    )

    # Advanced assets total
    advanced_assets_total = (
        stock_sub['total'] +
        retirement_sub['total'] +
        receivable_sub['total'] +
        business_sub['total'] +
        property_sub['total']
    )

    # Combined assets total
    assets_total = basic_assets_total + advanced_assets_total

    # Debts total (credit cards + adjusted loans + payables)
    debts_total = credit_card_sub['total'] + adjusted_loan_total + payables_sub['total']

    # Net total (assets minus debts, floored at 0)
    net_total = max(0, assets_total - debts_total)

    # For backward compatibility
    grand = assets_total

    # ==================== NISAB CALCULATION ====================
    nisab_gold_value = NISAB_GOLD_GRAMS * gold_price
    nisab_silver_value = NISAB_SILVER_GRAMS * silver_price

    if nisab_basis == 'silver':
        nisab_threshold = nisab_silver_value
    else:
        nisab_threshold = nisab_gold_value

    # Calculate ratio (clamped 0-1 for display)
    if nisab_threshold > 0:
        raw_ratio = net_total / nisab_threshold
        display_ratio = min(max(raw_ratio, 0), 1)
    else:
        raw_ratio = 0
        display_ratio = 0

    # Determine status
    if raw_ratio < 0.90:
        status = 'below'
    elif raw_ratio < 1.0:
        status = 'near'
    else:
        status = 'above'

    # Calculate difference and text
    difference = abs(net_total - nisab_threshold)
    if net_total >= nisab_threshold:
        difference_text = f"{round(difference, 2)} above nisab"
    else:
        difference_text = f"{round(difference, 2)} more to reach nisab"

    # Nisab check and zakat calculation
    above = net_total >= nisab_threshold
    zakat = round(net_total * ZAKAT_RATE, 2) if above else 0.0

    return {
        'base_currency': base_currency,
        'subtotals': {
            # Basic assets
            'gold': gold_sub,
            'cash': cash_sub,
            'bank': bank_sub,
            'metals': metal_sub,
            'crypto': crypto_sub,
            # Advanced assets
            'stocks': stock_sub,
            'retirement': retirement_sub,
            'receivables': receivable_sub,
            'business': business_sub,
            'property': property_sub,
            # Debts
            'debts': {
                'credit_cards': credit_card_sub,
                'loans': loan_sub,
                'short_term_payables': payables_sub,
            },
        },
        'basic_assets_total': round(basic_assets_total, 2),
        'advanced_assets_total': round(advanced_assets_total, 2),
        'assets_total': round(assets_total, 2),
        'debts_total': round(debts_total, 2),
        'debt_policy': debt_policy,
        'net_total': round(net_total, 2),
        'grand_total': round(grand, 2),
        'nisab': {
            'basis_used': nisab_basis,
            'gold_grams': NISAB_GOLD_GRAMS,
            'gold_threshold': round(nisab_gold_value, 2),
            'silver_grams': NISAB_SILVER_GRAMS,
            'silver_threshold': round(nisab_silver_value, 2),
            'threshold_used': round(nisab_threshold, 2),
            'ratio': round(display_ratio, 4),
            'status': status,
            'difference': round(difference, 2),
            'difference_text': difference_text,
        },
        'above_nisab': above,
        'zakat_due': zakat,
        'zakat_rate': ZAKAT_RATE,
    }
