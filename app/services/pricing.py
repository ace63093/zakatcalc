"""Pricing service with caching."""
from datetime import datetime, timezone
from . import cache


def generate_stub_pricing() -> dict:
    return {
        'base_currency': 'USD',
        'fx_rates': {'USD': 1.0, 'CAD': 1.38, 'BDT': 110.0},
        'metals': {
            'gold': {'price_per_gram_usd': 65.0, 'nisab_grams': 85},
            'silver': {'price_per_gram_usd': 0.82, 'nisab_grams': 595}
        },
        'zakat_rate': 0.025,
        'as_of': datetime.now(timezone.utc).isoformat(),
        'ttl_seconds': cache.DEFAULT_TTL
    }


def get_pricing(force_refresh: bool = False) -> tuple[dict, str]:
    """Returns (pricing_data, cache_status)."""
    if not force_refresh:
        cached = cache.read_cache()
        if cached:
            return (cached, 'hit')
    data = generate_stub_pricing()
    cache.write_cache(data)
    status = 'refreshed' if force_refresh else 'miss'
    return (data, status)


def format_pricing_response(data: dict, cache_status: str) -> dict:
    return {**data, 'cache_status': cache_status}
