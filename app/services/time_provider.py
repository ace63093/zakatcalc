"""Time provider abstraction for testable date handling.

All dates in this module are UTC. The system uses UTC midnight as the
canonical "today" for all cadence calculations.

This module provides a TimeProvider class that can be frozen for testing,
allowing deterministic tests that don't depend on the actual current date.
"""
from datetime import date, timezone, datetime
from typing import Optional


class TimeProvider:
    """Provides the current date, allowing tests to freeze time.

    Usage:
        # Production: uses real UTC date
        provider = TimeProvider()
        today = provider.today()

        # Testing: freeze to specific date
        provider = TimeProvider(frozen_date=date(2026, 1, 15))
        today = provider.today()  # Always returns 2026-01-15

    Note: All dates are UTC. The provider returns date objects (not datetime)
    representing UTC midnight.
    """

    _instance: Optional['TimeProvider'] = None

    def __init__(self, frozen_date: Optional[date] = None):
        """Initialize TimeProvider.

        Args:
            frozen_date: If provided, today() always returns this date.
                        Used for testing. If None, returns actual UTC date.
        """
        self._frozen_date = frozen_date

    def today(self) -> date:
        """Get current UTC date.

        Returns:
            date: Current UTC date, or frozen date if set.
        """
        if self._frozen_date is not None:
            return self._frozen_date
        return datetime.now(timezone.utc).date()

    @classmethod
    def get_default(cls) -> 'TimeProvider':
        """Get the default TimeProvider instance (singleton for production)."""
        if cls._instance is None:
            cls._instance = TimeProvider()
        return cls._instance

    @classmethod
    def set_default(cls, provider: 'TimeProvider') -> None:
        """Set the default TimeProvider (for testing)."""
        cls._instance = provider

    @classmethod
    def reset_default(cls) -> None:
        """Reset to production TimeProvider."""
        cls._instance = None


def get_today(time_provider: Optional[TimeProvider] = None) -> date:
    """Convenience function to get today's date.

    Args:
        time_provider: Optional TimeProvider. Uses default if not provided.

    Returns:
        Current UTC date.
    """
    if time_provider is None:
        time_provider = TimeProvider.get_default()
    return time_provider.today()
