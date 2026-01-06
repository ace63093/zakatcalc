"""Configuration service for pricing sync and app settings."""
import os


def is_sync_enabled() -> bool:
    """Check if network sync is allowed.

    Controlled by PRICING_ALLOW_NETWORK env var (default: 1/true for auto-sync).
    """
    return os.environ.get('PRICING_ALLOW_NETWORK', '1').lower() in ('1', 'true', 'yes')


def is_auto_sync_enabled() -> bool:
    """Check if auto-sync is enabled (new default: ON).

    Controlled by PRICING_AUTO_SYNC env var (default: 1/true).
    Only effective if network sync is also enabled.
    """
    if not is_sync_enabled():
        return False
    return os.environ.get('PRICING_AUTO_SYNC', '1').lower() in ('1', 'true', 'yes')


def is_auto_fetch_enabled() -> bool:
    """Check if auto-fetch for missing dates is enabled (alias for is_auto_sync_enabled).

    Kept for backward compatibility. Use is_auto_sync_enabled() for new code.
    """
    return is_auto_sync_enabled()


def get_storage_base_currency() -> str:
    """Get the base currency for storage. Always USD."""
    return 'USD'


def get_user_agent() -> str:
    """Get the User-Agent string for provider HTTP requests."""
    default_ua = 'ZakatCalculator/1.0 (https://github.com/zakat-app)'
    return os.environ.get('PRICING_SYNC_USER_AGENT', default_ua)


def get_recent_window_days() -> int:
    """Get the number of days for weekly cadence window.

    Controlled by PRICING_RECENT_DAYS env var (default: 31).
    """
    return int(os.environ.get('PRICING_RECENT_DAYS', '31'))


def get_sync_interval_seconds() -> int:
    """Get the daemon sync interval in seconds.

    Controlled by PRICING_SYNC_INTERVAL_SECONDS env var (default: 21600 = 6 hours).
    """
    return int(os.environ.get('PRICING_SYNC_INTERVAL_SECONDS', '21600'))


def get_lookback_months() -> int:
    """Get how many months of history to maintain.

    Controlled by PRICING_LOOKBACK_MONTHS env var (default: 12).
    """
    return int(os.environ.get('PRICING_LOOKBACK_MONTHS', '12'))


def get_sync_config() -> dict:
    """Get complete sync configuration status."""
    return {
        'sync_enabled': is_sync_enabled(),
        'auto_sync_enabled': is_auto_sync_enabled(),
        'storage_base_currency': get_storage_base_currency(),
        'recent_window_days': get_recent_window_days(),
        'sync_interval_seconds': get_sync_interval_seconds(),
        'lookback_months': get_lookback_months(),
        'user_agent': get_user_agent(),
    }


# Provider API key getters
def get_openexchangerates_key() -> str | None:
    """Get Open Exchange Rates API key if configured."""
    return os.environ.get('OPENEXCHANGERATES_APP_ID')


def get_goldapi_key() -> str | None:
    """Get GoldAPI key if configured."""
    return os.environ.get('GOLDAPI_KEY')


def get_coinmarketcap_key() -> str | None:
    """Get CoinMarketCap API key if configured."""
    return os.environ.get('COINMARKETCAP_API_KEY')


def get_provider_keys_status() -> dict:
    """Get status of configured provider API keys."""
    return {
        'openexchangerates': bool(get_openexchangerates_key()),
        'goldapi': bool(get_goldapi_key()),
        'coinmarketcap': bool(get_coinmarketcap_key()),
    }
