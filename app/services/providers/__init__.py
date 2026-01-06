"""Pluggable pricing data provider interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class FXRate:
    """FX rate data point."""
    currency: str       # ISO 4217 code
    rate_to_usd: float  # 1 USD = X currency
    source: str


@dataclass
class MetalPrice:
    """Metal price data point."""
    metal: str                  # gold, silver, platinum, palladium
    price_per_gram_usd: float
    source: str


@dataclass
class CryptoPrice:
    """Cryptocurrency price data point."""
    symbol: str
    name: str
    price_usd: float
    rank: Optional[int]
    source: str


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    records_count: int
    error_message: Optional[str] = None
    partial: bool = False


class FXProvider(ABC):
    """Abstract base for FX rate providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider needs an API key."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured (API key set if required)."""
        pass

    @abstractmethod
    def get_rates(self, target_date: date) -> list[FXRate]:
        """Fetch FX rates for a specific date.

        Args:
            target_date: Date to fetch rates for

        Returns:
            List of FXRate objects

        Raises:
            ProviderError: If fetch fails
        """
        pass


class MetalProvider(ABC):
    """Abstract base for metal price providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider needs an API key."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured."""
        pass

    @abstractmethod
    def get_prices(self, target_date: date) -> list[MetalPrice]:
        """Fetch metal prices for a specific date."""
        pass


class CryptoProvider(ABC):
    """Abstract base for cryptocurrency price providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider needs an API key."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured."""
        pass

    @abstractmethod
    def get_prices(self, target_date: date, symbols: list[str] | None = None) -> list[CryptoPrice]:
        """Fetch crypto prices for a specific date."""
        pass

    @abstractmethod
    def get_top_assets(self, limit: int = 100) -> list[tuple[str, str, int]]:
        """Fetch top cryptocurrencies by market cap.

        Returns:
            List of (symbol, name, rank) tuples
        """
        pass


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class RateLimitError(ProviderError):
    """API rate limit exceeded."""
    pass


class AuthenticationError(ProviderError):
    """API key invalid or missing."""
    pass


class NetworkError(ProviderError):
    """Network connectivity issue."""
    pass
