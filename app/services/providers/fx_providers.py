"""FX rate provider implementations."""
import json
import urllib.request
import urllib.error
from datetime import date, datetime
from typing import Optional

from app.services.config import get_openexchangerates_key, get_user_agent
from . import FXProvider, FXRate, ProviderError, RateLimitError, NetworkError


class ExchangeRateAPIProvider(FXProvider):
    """ExchangeRate-API provider - free tier without API key.

    Provides USD-based rates for major currencies.
    Free tier: ~1500 requests/month, current rates only.
    """

    BASE_URL = "https://open.er-api.com/v6"

    @property
    def name(self) -> str:
        return "exchangerate-api"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True  # No key required

    def get_rates(self, target_date: date) -> list[FXRate]:
        """Fetch FX rates. Note: Free tier only supports latest rates."""
        url = f"{self.BASE_URL}/latest/USD"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get('result') != 'success':
                raise ProviderError(f"API error: {data.get('error-type', 'unknown')}")

            rates = []
            for currency, rate in data.get('rates', {}).items():
                rates.append(FXRate(
                    currency=currency,
                    rate_to_usd=float(rate),
                    source=self.name
                ))

            return rates

        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError("Rate limit exceeded")
            raise ProviderError(f"HTTP error: {e.code}")
        except urllib.error.URLError as e:
            raise NetworkError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ProviderError("Invalid JSON response")


class OpenExchangeRatesProvider(FXProvider):
    """Open Exchange Rates provider - requires API key.

    Provides historical and current USD-based rates.
    Free tier: 1000 requests/month, historical data available.
    """

    BASE_URL = "https://openexchangerates.org/api"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or get_openexchangerates_key()

    @property
    def name(self) -> str:
        return "openexchangerates"

    @property
    def requires_api_key(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_rates(self, target_date: date) -> list[FXRate]:
        """Fetch FX rates for a specific date."""
        if not self._api_key:
            raise ProviderError("API key not configured")

        # Use historical endpoint for past dates, latest for today
        today = datetime.now().date()
        if target_date >= today:
            url = f"{self.BASE_URL}/latest.json?app_id={self._api_key}"
        else:
            date_str = target_date.strftime('%Y-%m-%d')
            url = f"{self.BASE_URL}/historical/{date_str}.json?app_id={self._api_key}"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            if 'error' in data:
                raise ProviderError(f"API error: {data.get('message', 'unknown')}")

            rates = []
            for currency, rate in data.get('rates', {}).items():
                rates.append(FXRate(
                    currency=currency,
                    rate_to_usd=float(rate),
                    source=self.name
                ))

            return rates

        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError("Rate limit exceeded")
            if e.code == 401:
                raise ProviderError("Invalid API key")
            raise ProviderError(f"HTTP error: {e.code}")
        except urllib.error.URLError as e:
            raise NetworkError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ProviderError("Invalid JSON response")


class FallbackFXProvider(FXProvider):
    """Fallback provider that returns empty list - for when no providers work."""

    @property
    def name(self) -> str:
        return "fallback"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True

    def get_rates(self, target_date: date) -> list[FXRate]:
        """Return empty list - indicates no external rates available."""
        return []
