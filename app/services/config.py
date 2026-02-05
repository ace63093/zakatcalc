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


def get_metalpriceapi_key() -> str | None:
    """Get MetalPriceAPI key if configured."""
    return os.environ.get('METALPRICEAPI_KEY')


def get_coinmarketcap_key() -> str | None:
    """Get CoinMarketCap API key if configured."""
    return os.environ.get('COINMARKETCAP_API_KEY')


def get_metalsdev_key() -> str | None:
    """Get Metals.dev API key if configured."""
    return os.environ.get('METALS_DEV_API_KEY')


def get_provider_keys_status() -> dict:
    """Get status of configured provider API keys."""
    return {
        'openexchangerates': bool(get_openexchangerates_key()),
        'goldapi': bool(get_goldapi_key()),
        'metalpriceapi': bool(get_metalpriceapi_key()),
        'metalsdev': bool(get_metalsdev_key()),
        'coinmarketcap': bool(get_coinmarketcap_key()),
    }


# ============================================================
# Feature Flags for Calculator Enhancements
# ============================================================

def is_advanced_assets_enabled() -> bool:
    """Check if advanced assets mode is enabled.

    Controlled by ENABLE_ADVANCED_ASSETS env var (default: 1/true).
    When enabled, users can toggle advanced mode to see stocks, retirement, etc.
    """
    return os.environ.get('ENABLE_ADVANCED_ASSETS', '1').lower() in ('1', 'true', 'yes')


def is_date_assistant_enabled() -> bool:
    """Check if zakat date assistant is enabled.

    Controlled by ENABLE_DATE_ASSISTANT env var (default: 1/true).
    When enabled, users can set zakat anniversary and get calendar reminders.
    """
    return os.environ.get('ENABLE_DATE_ASSISTANT', '1').lower() in ('1', 'true', 'yes')


def is_autosave_enabled() -> bool:
    """Check if localStorage autosave is enabled.

    Controlled by ENABLE_AUTOSAVE env var (default: 1/true).
    When enabled, calculator state is saved to localStorage automatically.
    """
    return os.environ.get('ENABLE_AUTOSAVE', '1').lower() in ('1', 'true', 'yes')


def is_print_summary_enabled() -> bool:
    """Check if printable summary feature is enabled.

    Controlled by ENABLE_PRINT_SUMMARY env var (default: 1/true).
    When enabled, /summary route renders a print-friendly breakdown.
    """
    return os.environ.get('ENABLE_PRINT_SUMMARY', '1').lower() in ('1', 'true', 'yes')


def get_canonical_host() -> str:
    """Get the canonical host for SEO.

    Controlled by CANONICAL_HOST env var (default: whatismyzakat.com).
    """
    return os.environ.get('CANONICAL_HOST', 'whatismyzakat.com')


def get_feature_flags() -> dict:
    """Get all feature flag statuses."""
    return {
        'advanced_assets_enabled': is_advanced_assets_enabled(),
        'date_assistant_enabled': is_date_assistant_enabled(),
        'autosave_enabled': is_autosave_enabled(),
        'print_summary_enabled': is_print_summary_enabled(),
        'canonical_host': get_canonical_host(),
    }
