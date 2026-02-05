"""FX rate provider implementations."""
import json
import urllib.request
import urllib.error
from datetime import date, datetime
from typing import Optional

from app.services.config import get_openexchangerates_key, get_user_agent
from . import FXProvider, FXRate, ProviderError, RateLimitError, NetworkError


class FawazExchangeAPIProvider(FXProvider):
    """fawazahmed0/exchange-api provider (via jsDelivr with Cloudflare fallback).

    Provides historical and latest USD-based rates with no API key.
    """

    BASE_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api"
    FALLBACK_URL = "https://{date}.currency-api.pages.dev"
    API_VERSION = "v1"
    BASE_CURRENCY = "usd"

    @property
    def name(self) -> str:
        return "fawaz-exchange-api"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True  # No key required

    def get_rates(self, target_date: date) -> list[FXRate]:
        """Fetch FX rates for a specific date (or latest)."""
        today = datetime.now().date()
        date_str = "latest" if target_date >= today else target_date.strftime('%Y-%m-%d')

        endpoints = [
            f"{self.BASE_URL}@{date_str}/{self.API_VERSION}/currencies/{self.BASE_CURRENCY}.min.json",
            f"{self.FALLBACK_URL.format(date=date_str)}/{self.API_VERSION}/currencies/{self.BASE_CURRENCY}.min.json",
            f"{self.BASE_URL}@{date_str}/{self.API_VERSION}/currencies/{self.BASE_CURRENCY}.json",
            f"{self.FALLBACK_URL.format(date=date_str)}/{self.API_VERSION}/currencies/{self.BASE_CURRENCY}.json",
        ]

        last_error = None
        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))

                rates_blob = data.get(self.BASE_CURRENCY)
                if not isinstance(rates_blob, dict):
                    raise ProviderError("Unexpected response format")

                rates = []
                for currency, rate in rates_blob.items():
                    try:
                        rate_value = float(rate)
                    except (TypeError, ValueError):
                        continue

                    rates.append(FXRate(
                        currency=str(currency).upper(),
                        rate_to_usd=rate_value,
                        source=self.name
                    ))

                if not any(r.currency == 'USD' for r in rates):
                    rates.append(FXRate(currency='USD', rate_to_usd=1.0, source=self.name))

                return rates

            except urllib.error.HTTPError as e:
                last_error = e
                if e.code == 429:
                    raise RateLimitError("Rate limit exceeded")
                continue
            except urllib.error.URLError as e:
                last_error = e
                continue
            except json.JSONDecodeError as e:
                last_error = e
                continue

        if last_error:
            raise ProviderError(f"Failed to fetch rates: {last_error}")
        raise ProviderError("Failed to fetch rates")


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


class ChainedFXProvider(FXProvider):
    """Try a primary provider, then fall back when needed."""

    def __init__(self, primary: FXProvider, fallback: FXProvider):
        self._primary = primary
        self._fallback = fallback
        self._last_provider = primary

    @property
    def name(self) -> str:
        return self._last_provider.name

    @property
    def requires_api_key(self) -> bool:
        return self._primary.requires_api_key and self._fallback.requires_api_key

    def is_configured(self) -> bool:
        return self._primary.is_configured() or self._fallback.is_configured()

    def _should_use_primary(self, target_date: date) -> bool:
        if isinstance(self._primary, ExchangeRateAPIProvider):
            today = datetime.now().date()
            if target_date < today:
                return False
        return True

    def get_rates(self, target_date: date) -> list[FXRate]:
        """Fetch FX rates using primary, with fallback on failure or unsupported dates."""
        primary_error = None

        if self._should_use_primary(target_date):
            try:
                rates = self._primary.get_rates(target_date)
                if rates:
                    self._last_provider = self._primary
                    return rates
            except (RateLimitError, NetworkError, ProviderError) as exc:
                primary_error = exc

        try:
            rates = self._fallback.get_rates(target_date)
            if rates:
                self._last_provider = self._fallback
                return rates
        except (RateLimitError, NetworkError, ProviderError) as exc:
            raise exc

        if primary_error:
            raise ProviderError(f"Primary provider failed: {primary_error}")
        raise ProviderError("No rates returned from providers")


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
