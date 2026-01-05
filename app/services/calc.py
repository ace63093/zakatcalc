"""Zakat calculation service."""
from .fx import convert_to_master

VALID_KARATS = [24, 22, 21, 18, 14, 10, 9]
ZAKAT_RATE = 0.025
NISAB_GOLD_GRAMS = 85


def karat_to_fraction(karat: int) -> float:
    """Convert karat to purity fraction. 24K=1.0, 18K=0.75, etc."""
    return karat / 24.0


def calculate_pure_grams(weight: float, karat: int) -> float:
    return weight * karat_to_fraction(karat)


def calculate_gold_subtotal(gold_items: list, gold_price_usd: float, master_currency: str, fx_rates: dict) -> dict:
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


def calculate_zakat(gold_items: list, cash_items: list, bank_items: list, master_currency: str, pricing: dict) -> dict:
    fx = pricing.get('fx_rates', {})
    gold_price = pricing.get('metals', {}).get('gold', {}).get('price_per_gram_usd', 65.0)
    gold_sub = calculate_gold_subtotal(gold_items, gold_price, master_currency, fx)
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
