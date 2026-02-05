"""Provider registry and selection logic."""
from app.services.config import (
    get_openexchangerates_key,
    get_goldapi_key,
    get_metalsdev_key,
    get_metalpriceapi_key,
    get_coinmarketcap_key,
)
from . import FXProvider, MetalProvider, CryptoProvider
from .fx_providers import (
    ExchangeRateAPIProvider,
    OpenExchangeRatesProvider,
    FawazExchangeAPIProvider,
    ChainedFXProvider,
)
from .metal_providers import MetalPriceAPIProvider, MetalsDevAPIProvider, GoldAPIProvider, FallbackMetalProvider
from .crypto_providers import CoinGeckoProvider, CoinMarketCapProvider, FallbackCryptoProvider


def get_fx_provider() -> FXProvider:
    """Get configured FX provider based on available API keys.

    Priority:
    1. OpenExchangeRates (if key configured) - best historical support
    2. ExchangeRateAPI (no key) - current rates only
       (falls back to Fawaz Exchange API for historical/failed requests)
    """
    if get_openexchangerates_key():
        return OpenExchangeRatesProvider()
    return ChainedFXProvider(
        primary=ExchangeRateAPIProvider(),
        fallback=FawazExchangeAPIProvider(),
    )


def get_metal_provider() -> MetalProvider:
    """Get configured metal provider.

    Priority:
    1. MetalPriceAPI (if key configured) - preferred for current pricing
    2. GoldAPI (if key configured) - best historical support
    3. MetalsDevAPI (if key configured) - current prices only
    4. Fallback (empty results)
    """
    if get_metalpriceapi_key():
        return MetalPriceAPIProvider()
    if get_goldapi_key():
        return GoldAPIProvider()
    if get_metalsdev_key():
        return MetalsDevAPIProvider()
    return FallbackMetalProvider()


def get_crypto_provider() -> CryptoProvider:
    """Get configured crypto provider.

    Priority:
    1. CoinMarketCap (if key configured) - best data quality
    2. CoinGecko (no key) - rate limited but works
    3. Fallback (empty results)
    """
    if get_coinmarketcap_key():
        return CoinMarketCapProvider()
    return CoinGeckoProvider()


def get_provider_status() -> dict:
    """Return status of all configured providers."""
    fx = get_fx_provider()
    metal = get_metal_provider()
    crypto = get_crypto_provider()

    return {
        'fx': {
            'provider': fx.name,
            'requires_key': fx.requires_api_key,
            'configured': fx.is_configured(),
        },
        'metals': {
            'provider': metal.name,
            'requires_key': metal.requires_api_key,
            'configured': metal.is_configured(),
        },
        'crypto': {
            'provider': crypto.name,
            'requires_key': crypto.requires_api_key,
            'configured': crypto.is_configured(),
        },
    }


def get_all_providers() -> dict:
    """Get all provider instances."""
    return {
        'fx': get_fx_provider(),
        'metals': get_metal_provider(),
        'crypto': get_crypto_provider(),
    }
