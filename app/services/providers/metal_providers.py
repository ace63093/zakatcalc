"""Metal price provider implementations."""
import json
import urllib.request
import urllib.error
from datetime import date, datetime
from typing import Optional

from app.services.config import get_goldapi_key, get_metalsdev_key, get_user_agent
from . import MetalProvider, MetalPrice, ProviderError, RateLimitError, NetworkError


# Conversion constant: troy ounce to grams
TROY_OZ_TO_GRAMS = 31.1035


class MetalsDevAPIProvider(MetalProvider):
    """Metals.dev API provider - free tier available.

    Provides USD-based prices for gold, silver, platinum, palladium.
    Free tier: 1000 requests/month for latest prices.
    """

    BASE_URL = "https://api.metals.dev/v1"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or get_metalsdev_key()

    @property
    def name(self) -> str:
        return "metals-dev"

    @property
    def requires_api_key(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_prices(self, target_date: date) -> list[MetalPrice]:
        """Fetch metal prices. Free tier only supports latest prices."""
        if not self._api_key:
            raise ProviderError("Metals.dev API key not configured")

        url = f"{self.BASE_URL}/latest?api_key={self._api_key}&currency=USD&unit=toz"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get('status') != 'success':
                raise ProviderError(f"API error: {data.get('error', 'unknown')}")

            metals_data = data.get('metals', {})
            prices = []

            # Map API symbols to our metal names
            symbol_map = {
                'XAU': 'gold',
                'XAG': 'silver',
                'XPT': 'platinum',
                'XPD': 'palladium',
            }

            for symbol, metal_name in symbol_map.items():
                price_per_oz = metals_data.get(symbol)
                if price_per_oz is not None:
                    price_per_gram = float(price_per_oz) / TROY_OZ_TO_GRAMS
                    prices.append(MetalPrice(
                        metal=metal_name,
                        price_per_gram_usd=round(price_per_gram, 4),
                        source=self.name
                    ))

            return prices

        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError("Rate limit exceeded")
            raise ProviderError(f"HTTP error: {e.code}")
        except urllib.error.URLError as e:
            raise NetworkError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ProviderError("Invalid JSON response")


class GoldAPIProvider(MetalProvider):
    """GoldAPI.io provider - requires API key.

    Provides historical and current USD-based prices for precious metals.
    Free tier: 300 requests/month.
    """

    BASE_URL = "https://www.goldapi.io/api"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or get_goldapi_key()

    @property
    def name(self) -> str:
        return "goldapi"

    @property
    def requires_api_key(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_prices(self, target_date: date) -> list[MetalPrice]:
        """Fetch metal prices for a specific date."""
        if not self._api_key:
            raise ProviderError("API key not configured")

        prices = []
        symbols = ['XAU', 'XAG', 'XPT', 'XPD']
        symbol_map = {
            'XAU': 'gold',
            'XAG': 'silver',
            'XPT': 'platinum',
            'XPD': 'palladium',
        }

        today = datetime.now().date()
        date_str = target_date.strftime('%Y%m%d') if target_date < today else None

        for symbol in symbols:
            try:
                if date_str:
                    url = f"{self.BASE_URL}/{symbol}/USD/{date_str}"
                else:
                    url = f"{self.BASE_URL}/{symbol}/USD"

                req = urllib.request.Request(url, headers={
                    'User-Agent': get_user_agent(),
                    'x-access-token': self._api_key,
                })
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))

                price_per_oz = data.get('price')
                if price_per_oz is not None:
                    price_per_gram = float(price_per_oz) / TROY_OZ_TO_GRAMS
                    prices.append(MetalPrice(
                        metal=symbol_map[symbol],
                        price_per_gram_usd=round(price_per_gram, 4),
                        source=self.name
                    ))

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise RateLimitError("Rate limit exceeded")
                if e.code == 401:
                    raise ProviderError("Invalid API key")
                # Continue with other metals on other errors
                continue
            except urllib.error.URLError as e:
                raise NetworkError(f"Network error: {e.reason}")
            except json.JSONDecodeError:
                continue

        return prices


class FallbackMetalProvider(MetalProvider):
    """Fallback provider that returns empty list."""

    @property
    def name(self) -> str:
        return "fallback"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True

    def get_prices(self, target_date: date) -> list[MetalPrice]:
        """Return empty list - indicates no external prices available."""
        return []
