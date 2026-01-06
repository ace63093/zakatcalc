"""Cryptocurrency price provider implementations."""
import json
import urllib.request
import urllib.error
from datetime import date, datetime
from typing import Optional
import time

from app.services.config import get_coinmarketcap_key, get_user_agent
from . import CryptoProvider, CryptoPrice, ProviderError, RateLimitError, NetworkError


class CoinGeckoProvider(CryptoProvider):
    """CoinGecko API provider - no API key required (rate-limited).

    Provides USD-based prices for cryptocurrencies.
    Free tier: 10-30 calls/minute without key.
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    # CoinGecko uses IDs different from symbols, maintain a mapping for top coins
    SYMBOL_TO_ID = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'USDT': 'tether',
        'BNB': 'binancecoin',
        'SOL': 'solana',
        'XRP': 'ripple',
        'USDC': 'usd-coin',
        'ADA': 'cardano',
        'AVAX': 'avalanche-2',
        'DOGE': 'dogecoin',
        'TRX': 'tron',
        'DOT': 'polkadot',
        'LINK': 'chainlink',
        'MATIC': 'matic-network',
        'TON': 'the-open-network',
        'SHIB': 'shiba-inu',
        'LTC': 'litecoin',
        'BCH': 'bitcoin-cash',
        'UNI': 'uniswap',
        'XLM': 'stellar',
        'ATOM': 'cosmos',
        'XMR': 'monero',
        'ETC': 'ethereum-classic',
        'FIL': 'filecoin',
        'HBAR': 'hedera-hashgraph',
        'APT': 'aptos',
        'ARB': 'arbitrum',
        'NEAR': 'near',
        'VET': 'vechain',
        'OP': 'optimism',
    }

    @property
    def name(self) -> str:
        return "coingecko"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True

    def get_prices(self, target_date: date, symbols: list[str] | None = None) -> list[CryptoPrice]:
        """Fetch crypto prices for a specific date."""
        prices = []

        # Use markets endpoint for current prices
        today = datetime.now().date()

        if target_date >= today:
            # Current prices via markets endpoint
            return self._get_current_prices(symbols)
        else:
            # Historical prices - need to fetch per coin
            return self._get_historical_prices(target_date, symbols)

    def _get_current_prices(self, symbols: list[str] | None = None) -> list[CryptoPrice]:
        """Fetch current prices for top 100 cryptocurrencies."""
        url = f"{self.BASE_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            prices = []
            for coin in data:
                symbol = coin.get('symbol', '').upper()
                if symbols and symbol not in symbols:
                    continue

                prices.append(CryptoPrice(
                    symbol=symbol,
                    name=coin.get('name', ''),
                    price_usd=float(coin.get('current_price', 0)),
                    rank=coin.get('market_cap_rank'),
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

    def _get_historical_prices(self, target_date: date, symbols: list[str] | None = None) -> list[CryptoPrice]:
        """Fetch historical prices - limited by rate limits."""
        prices = []
        date_str = target_date.strftime('%d-%m-%Y')

        # Limit to specific symbols or top coins from mapping
        coins_to_fetch = symbols if symbols else list(self.SYMBOL_TO_ID.keys())[:20]

        for symbol in coins_to_fetch:
            coin_id = self.SYMBOL_TO_ID.get(symbol)
            if not coin_id:
                continue

            url = f"{self.BASE_URL}/coins/{coin_id}/history?date={date_str}"

            try:
                time.sleep(0.5)  # Rate limit protection
                req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))

                market_data = data.get('market_data', {})
                price = market_data.get('current_price', {}).get('usd')
                if price:
                    prices.append(CryptoPrice(
                        symbol=symbol,
                        name=data.get('name', ''),
                        price_usd=float(price),
                        rank=data.get('market_cap_rank'),
                        source=self.name
                    ))

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise RateLimitError("Rate limit exceeded")
                continue
            except (urllib.error.URLError, json.JSONDecodeError):
                continue

        return prices

    def get_top_assets(self, limit: int = 100) -> list[tuple[str, str, int]]:
        """Fetch top cryptocurrencies by market cap."""
        url = f"{self.BASE_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': get_user_agent()})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            assets = []
            for coin in data:
                symbol = coin.get('symbol', '').upper()
                name = coin.get('name', '')
                rank = coin.get('market_cap_rank', 0)
                if symbol and name and rank:
                    assets.append((symbol, name, rank))

            return assets

        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            return []


class CoinMarketCapProvider(CryptoProvider):
    """CoinMarketCap API provider - requires API key.

    Provides historical and current USD-based prices.
    Free tier: 333 calls/day.
    """

    BASE_URL = "https://pro-api.coinmarketcap.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or get_coinmarketcap_key()

    @property
    def name(self) -> str:
        return "coinmarketcap"

    @property
    def requires_api_key(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_prices(self, target_date: date, symbols: list[str] | None = None) -> list[CryptoPrice]:
        """Fetch crypto prices."""
        if not self._api_key:
            raise ProviderError("API key not configured")

        url = f"{self.BASE_URL}/cryptocurrency/listings/latest?limit=100&convert=USD"

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': get_user_agent(),
                'X-CMC_PRO_API_KEY': self._api_key,
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get('status', {}).get('error_code'):
                raise ProviderError(f"API error: {data['status'].get('error_message')}")

            prices = []
            for coin in data.get('data', []):
                symbol = coin.get('symbol', '').upper()
                if symbols and symbol not in symbols:
                    continue

                quote = coin.get('quote', {}).get('USD', {})
                prices.append(CryptoPrice(
                    symbol=symbol,
                    name=coin.get('name', ''),
                    price_usd=float(quote.get('price', 0)),
                    rank=coin.get('cmc_rank'),
                    source=self.name
                ))

            return prices

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

    def get_top_assets(self, limit: int = 100) -> list[tuple[str, str, int]]:
        """Fetch top cryptocurrencies."""
        if not self._api_key:
            return []

        url = f"{self.BASE_URL}/cryptocurrency/listings/latest?limit={limit}&convert=USD"

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': get_user_agent(),
                'X-CMC_PRO_API_KEY': self._api_key,
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            assets = []
            for coin in data.get('data', []):
                symbol = coin.get('symbol', '').upper()
                name = coin.get('name', '')
                rank = coin.get('cmc_rank', 0)
                if symbol and name and rank:
                    assets.append((symbol, name, rank))

            return assets

        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            return []


class FallbackCryptoProvider(CryptoProvider):
    """Fallback provider that returns empty list."""

    @property
    def name(self) -> str:
        return "fallback"

    @property
    def requires_api_key(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return True

    def get_prices(self, target_date: date, symbols: list[str] | None = None) -> list[CryptoPrice]:
        """Return empty list."""
        return []

    def get_top_assets(self, limit: int = 100) -> list[tuple[str, str, int]]:
        """Return empty list."""
        return []
