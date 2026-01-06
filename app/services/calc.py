"""Zakat calculation service."""
from .fx import convert_to_master

VALID_KARATS = [24, 22, 21, 18, 14, 10, 9]
ZAKAT_RATE = 0.025
NISAB_GOLD_GRAMS = 85
NISAB_SILVER_GRAMS = 595


def karat_to_fraction(karat: int) -> float:
    """Convert karat to purity fraction. 24K=1.0, 18K=0.75, etc."""
    return karat / 24.0


def calculate_pure_grams(weight: float, karat: int) -> float:
    return weight * karat_to_fraction(karat)


def calculate_gold_subtotal(gold_items: list, gold_price: float, base_currency: str, fx_rates: dict) -> dict:
    """Calculate gold subtotal. Gold price should already be in base currency."""
    items_out = []
    total_pure = 0.0
    total_value = 0.0
    for item in gold_items:
        pure = calculate_pure_grams(item['weight_grams'], item['purity_karat'])
        # Gold price is already in base currency
        value = pure * gold_price
        items_out.append({
            'name': item.get('name', 'Gold'),
            'weight_grams': item['weight_grams'],
            'purity_karat': item['purity_karat'],
            'pure_grams': round(pure, 4),
            'value': round(value, 2)
        })
        total_pure += pure
        total_value += value
    return {'items': items_out, 'total_pure_grams': round(total_pure, 4), 'total': round(total_value, 2)}


def calculate_gold_subtotal_usd(gold_items: list, gold_price_usd: float, master_currency: str, fx_rates: dict) -> dict:
    """Calculate gold subtotal from USD price (legacy compatibility)."""
    items_out = []
    total_pure = 0.0
    total_value = 0.0
    for item in gold_items:
        pure = calculate_pure_grams(item['weight_grams'], item['purity_karat'])
        value_usd = pure * gold_price_usd
        value_master, rate = convert_to_master(value_usd, 'USD', master_currency, fx_rates)
        items_out.append({
            'name': item.get('name', 'Gold'),
            'weight_grams': item['weight_grams'],
            'purity_karat': item['purity_karat'],
            'pure_grams': round(pure, 4),
            'value': round(value_master, 2)
        })
        total_pure += pure
        total_value += value_master
    return {'items': items_out, 'total_pure_grams': round(total_pure, 4), 'total': round(total_value, 2)}


def calculate_cash_subtotal(cash_items: list, master_currency: str, fx_rates: dict) -> dict:
    items_out = []
    total = 0.0
    for item in cash_items:
        converted, rate = convert_to_master(item['amount'], item['currency'], master_currency, fx_rates)
        items_out.append({
            'name': item.get('name', 'Cash'),
            'original_currency': item['currency'],
            'original_amount': item['amount'],
            'converted_amount': round(converted, 2),
            'fx_rate': round(rate, 6)
        })
        total += converted
    return {'items': items_out, 'total': round(total, 2)}


def calculate_bank_subtotal(bank_items: list, master_currency: str, fx_rates: dict) -> dict:
    items_out = []
    total = 0.0
    for item in bank_items:
        converted, rate = convert_to_master(item['amount'], item['currency'], master_currency, fx_rates)
        items_out.append({
            'name': item.get('name', 'Bank'),
            'original_currency': item['currency'],
            'original_amount': item['amount'],
            'converted_amount': round(converted, 2),
            'fx_rate': round(rate, 6)
        })
        total += converted
    return {'items': items_out, 'total': round(total, 2)}


def calculate_metal_subtotal(metal_items: list, metal_prices: dict, base_currency: str) -> dict:
    """Calculate subtotal for other precious metals (silver, platinum, palladium).

    Args:
        metal_items: List of dicts with name, metal, weight_grams
        metal_prices: Dict of metal -> price_per_gram in base currency
        base_currency: The base currency (for reference only, prices already converted)

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in metal_items:
        metal_type = item.get('metal', '').lower()
        weight = item.get('weight_grams', 0)
        price_per_gram = metal_prices.get(metal_type, 0)
        value = weight * price_per_gram

        items_out.append({
            'name': item.get('name', metal_type.title()),
            'metal': metal_type,
            'weight_grams': weight,
            'price_per_gram': round(price_per_gram, 4),
            'value': round(value, 2)
        })
        total += value

    return {'items': items_out, 'total': round(total, 2)}


def calculate_crypto_subtotal(crypto_items: list, crypto_prices: dict, base_currency: str) -> dict:
    """Calculate subtotal for cryptocurrency assets.

    Args:
        crypto_items: List of dicts with name, symbol, amount
        crypto_prices: Dict of symbol -> {name, price, rank} in base currency
        base_currency: The base currency (for reference only, prices already converted)

    Returns:
        Dict with items list and total
    """
    items_out = []
    total = 0.0

    for item in crypto_items:
        symbol = item.get('symbol', '').upper()
        amount = item.get('amount', 0)

        crypto_info = crypto_prices.get(symbol, {})
        price_per_unit = crypto_info.get('price', 0) if isinstance(crypto_info, dict) else 0
        value = amount * price_per_unit

        items_out.append({
            'name': item.get('name', crypto_info.get('name', symbol) if isinstance(crypto_info, dict) else symbol),
            'symbol': symbol,
            'amount': amount,
            'price_per_unit': round(price_per_unit, 2),
            'value': round(value, 2)
        })
        total += value

    return {'items': items_out, 'total': round(total, 2)}


def calculate_zakat(gold_items: list, cash_items: list, bank_items: list, master_currency: str, pricing: dict) -> dict:
    """Legacy calculate_zakat for backward compatibility."""
    fx = pricing.get('fx_rates', {})
    gold_price = pricing.get('metals', {}).get('gold', {}).get('price_per_gram_usd', 65.0)
    gold_sub = calculate_gold_subtotal_usd(gold_items, gold_price, master_currency, fx)
    cash_sub = calculate_cash_subtotal(cash_items, master_currency, fx)
    bank_sub = calculate_bank_subtotal(bank_items, master_currency, fx)
    grand = gold_sub['total'] + cash_sub['total'] + bank_sub['total']
    nisab_usd = NISAB_GOLD_GRAMS * gold_price
    nisab_master, _ = convert_to_master(nisab_usd, 'USD', master_currency, fx)
    above = grand >= nisab_master
    zakat = round(grand * ZAKAT_RATE, 2) if above else 0.0
    return {
        'master_currency': master_currency,
        'subtotals': {'gold': gold_sub, 'cash': cash_sub, 'bank': bank_sub},
        'grand_total': round(grand, 2),
        'nisab_threshold': round(nisab_master, 2),
        'above_nisab': above,
        'zakat_due': zakat,
        'zakat_rate': ZAKAT_RATE,
        'pricing_metadata': {'as_of': pricing.get('as_of'), 'base_currency': pricing.get('base_currency')}
    }


def calculate_zakat_v2(
    gold_items: list,
    cash_items: list,
    bank_items: list,
    metal_items: list,
    crypto_items: list,
    base_currency: str,
    pricing: dict,
    nisab_basis: str = 'gold'
) -> dict:
    """Calculate zakat with all asset categories.

    Args:
        gold_items: List of gold items with name, weight_grams, purity_karat
        cash_items: List of cash items with name, currency, amount
        bank_items: List of bank items with name, currency, amount
        metal_items: List of other metal items with name, metal, weight_grams
        crypto_items: List of crypto items with name, symbol, amount
        base_currency: Target currency for all calculations
        pricing: Pricing snapshot with fx_rates, metals, crypto all in base_currency
        nisab_basis: "gold" or "silver" - which metal to use for nisab threshold

    Returns:
        Complete calculation result with all subtotals and zakat due
    """
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
    gold_price = metal_prices.get('gold', 0)
    silver_price = metal_prices.get('silver', 0)

    # Calculate subtotals
    gold_sub = calculate_gold_subtotal(gold_items, gold_price, base_currency, fx_rates)
    cash_sub = calculate_cash_subtotal(cash_items, base_currency, fx_rates)
    bank_sub = calculate_bank_subtotal(bank_items, base_currency, fx_rates)
    metal_sub = calculate_metal_subtotal(metal_items, metal_prices, base_currency)
    crypto_sub = calculate_crypto_subtotal(crypto_items, crypto_prices, base_currency)

    # Grand total
    grand = (
        gold_sub['total'] +
        cash_sub['total'] +
        bank_sub['total'] +
        metal_sub['total'] +
        crypto_sub['total']
    )

    # Calculate nisab thresholds
    nisab_gold_value = NISAB_GOLD_GRAMS * gold_price
    nisab_silver_value = NISAB_SILVER_GRAMS * silver_price

    # Determine threshold based on selected basis
    if nisab_basis == 'silver':
        nisab_threshold = nisab_silver_value
    else:
        nisab_threshold = nisab_gold_value

    # Calculate ratio (clamped 0-1 for display purposes)
    if nisab_threshold > 0:
        raw_ratio = grand / nisab_threshold
        display_ratio = min(max(raw_ratio, 0), 1)
    else:
        raw_ratio = 0
        display_ratio = 0

    # Determine status based on ratio
    if raw_ratio < 0.90:
        status = 'below'
    elif raw_ratio < 1.0:
        status = 'near'
    else:
        status = 'above'

    # Calculate difference and text
    difference = abs(grand - nisab_threshold)
    if grand >= nisab_threshold:
        difference_text = f"{round(difference, 2)} above nisab"
    else:
        difference_text = f"{round(difference, 2)} more to reach nisab"

    above = grand >= nisab_threshold
    zakat = round(grand * ZAKAT_RATE, 2) if above else 0.0

    return {
        'base_currency': base_currency,
        'subtotals': {
            'gold': gold_sub,
            'cash': cash_sub,
            'bank': bank_sub,
            'metals': metal_sub,
            'crypto': crypto_sub,
        },
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
