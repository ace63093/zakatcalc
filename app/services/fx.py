"""Currency conversion service."""
from app.data.currencies import get_currency_codes, is_valid_currency as _is_valid

# For backward compatibility, keep a short list but full validation uses ISO 4217
SUPPORTED_CURRENCIES = ['CAD', 'USD', 'BDT']
DEFAULT_MASTER = 'CAD'


def convert_to_master(amount: float, from_currency: str, master_currency: str, fx_rates: dict) -> tuple[float, float]:
    """Convert amount to master currency. Returns (converted, rate_used).

    This function handles two scenarios:
    1. If fx_rates contains rates as "how many base per 1 unit" (cross-rates to base):
       Then rate for from_currency is already the conversion factor.
    2. If fx_rates contains raw USD-based rates (1 USD = X currency):
       Then we need: master_rate / source_rate

    The db_pricing module provides cross-rates where:
    - fx_rates[base_currency] = 1.0
    - fx_rates[other] = conversion factor to base

    So if converting FROM 'other' currency TO base:
    - amount_in_base = amount * fx_rates[other]

    For converting from_currency to master_currency when both are in fx_rates:
    - If fx_rates is base=master_currency: amount * fx_rates[from_currency]
    - If fx_rates is base=something_else: need to chain the conversion
    """
    if from_currency == master_currency:
        return (amount, 1.0)

    # Handle the case where fx_rates[master_currency] == 1.0 (rates are relative to master)
    # In this case, fx_rates[X] means "1 master = X units of currency X"
    # So to convert FROM currency X TO master: amount / fx_rates[X]
    if fx_rates.get(master_currency) == 1.0:
        source_rate = fx_rates.get(from_currency, 1.0)
        if source_rate == 0:
            return (0.0, 0.0)
        rate = 1.0 / source_rate
        return (amount * rate, rate)

    # Otherwise, compute cross rate from USD-based rates
    source_rate = fx_rates.get(from_currency, 1.0)
    master_rate = fx_rates.get(master_currency, 1.0)
    if source_rate == 0:
        return (0.0, 0.0)
    rate = master_rate / source_rate
    return (amount * rate, rate)


def validate_currency(currency: str) -> bool:
    """Validate if a currency code is supported (any ISO 4217 currency)."""
    return _is_valid(currency)


def get_all_currency_codes() -> list[str]:
    """Get all supported currency codes in priority order."""
    return get_currency_codes()
