"""Currency conversion service."""
SUPPORTED_CURRENCIES = ['CAD', 'USD', 'BDT']
DEFAULT_MASTER = 'CAD'


def convert_to_master(amount: float, from_currency: str, master_currency: str, fx_rates: dict) -> tuple[float, float]:
    """Convert amount to master currency. Returns (converted, rate_used).
    Formula: amount * (fx_rates[master] / fx_rates[from_currency])
    """
    if from_currency == master_currency:
        return (amount, 1.0)
    source_rate = fx_rates.get(from_currency, 1.0)
    master_rate = fx_rates.get(master_currency, 1.0)
    rate = master_rate / source_rate
    return (amount * rate, rate)


def validate_currency(currency: str) -> bool:
    return currency in SUPPORTED_CURRENCIES
