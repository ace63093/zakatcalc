"""Snapshot cadence calculation utilities.

This module handles the mapping of requested dates to effective snapshot dates
based on a 3-tier cadence:

- DAILY snapshots for last 30 days (today - 29 to today, inclusive)
- WEEKLY snapshots (Mondays) for days 31-90 (today - 89 to today - 30)
- MONTHLY snapshots (1st of month) from 2000-01-01 to before weekly range

All dates are UTC. See time_provider.py for date handling.

Boundary Definitions:
    DAILY_WINDOW_DAYS = 30 days (days 0-29 from today)
    WEEKLY_WINDOW_DAYS = 60 days (days 30-89 from today)
    MONTHLY_START = date(2000, 1, 1)

Examples:
    Assuming today = 2026-01-15:
    - Request 2026-01-10 (5 days ago) -> daily, effective=2026-01-10
    - Request 2025-12-01 (45 days ago) -> weekly, effective=Monday on/before
    - Request 2025-06-15 (214 days ago) -> monthly, effective=2025-06-01
"""
from datetime import date, timedelta
from typing import Optional, Literal

from app.services.time_provider import TimeProvider, get_today


# Constants - document boundary definitions
DAILY_WINDOW_DAYS = 30   # Days 0-29 from today (30 days inclusive)
WEEKLY_WINDOW_DAYS = 60  # Days 30-89 from today (60 days total)
MONTHLY_START = date(2000, 1, 1)  # Earliest supported snapshot date

CadenceType = Literal['daily', 'weekly', 'monthly']


def get_effective_snapshot_date(
    requested: date,
    today: Optional[date] = None,
    time_provider: Optional[TimeProvider] = None
) -> tuple[date, CadenceType]:
    """Calculate the effective snapshot date for a requested date.

    Args:
        requested: The date the user is requesting pricing for
        today: Current date (for testing). If None, uses time_provider.
        time_provider: TimeProvider instance. Uses default if None.

    Returns:
        Tuple of (effective_snapshot_date, cadence_type)
        cadence_type is 'daily', 'weekly', or 'monthly'

    Algorithm:
        1. If requested is within last 30 days (days 0-29, inclusive):
           -> cadence='daily', effective_date=requested (no mapping)
        2. If requested is within days 30-89:
           -> cadence='weekly', effective_date=Monday on or before requested
        3. If requested is older than 89 days:
           -> cadence='monthly', effective_date=1st of month on or before
        4. If requested is before MONTHLY_START (2000-01-01):
           -> cadence='monthly', effective_date=MONTHLY_START

    Boundaries (inclusive):
        Daily:   [today - 29, today]
        Weekly:  [today - 89, today - 30]
        Monthly: [2000-01-01, today - 90]

    Examples:
        >>> # Assuming today = 2026-01-15
        >>> get_effective_snapshot_date(date(2026, 1, 10), date(2026, 1, 15))
        (date(2026, 1, 10), 'daily')  # 5 days ago, within daily window

        >>> get_effective_snapshot_date(date(2025, 12, 1), date(2026, 1, 15))
        (date(2025, 12, 1), 'weekly')  # 45 days ago, Dec 1 2025 is Monday

        >>> get_effective_snapshot_date(date(2025, 6, 15), date(2026, 1, 15))
        (date(2025, 6, 1), 'monthly')  # >90 days ago, mapped to 1st
    """
    if today is None:
        today = get_today(time_provider)

    # Calculate boundaries
    # Daily: days 0-29 (today to today-29, inclusive = 30 days)
    daily_cutoff = today - timedelta(days=DAILY_WINDOW_DAYS - 1)  # day 29
    # Weekly: days 30-89 (today-30 to today-89, inclusive = 60 days)
    weekly_cutoff = today - timedelta(days=DAILY_WINDOW_DAYS + WEEKLY_WINDOW_DAYS - 1)  # day 89

    # Handle dates before our data starts
    if requested < MONTHLY_START:
        return (MONTHLY_START, 'monthly')

    # Handle future dates (treat as today)
    if requested > today:
        return (today, 'daily')

    # Tier 1: Daily (last 30 days, days 0-29)
    if requested >= daily_cutoff:
        return (requested, 'daily')

    # Tier 2: Weekly (days 30-89)
    if requested >= weekly_cutoff:
        effective = get_monday_of_week(requested)
        return (effective, 'weekly')

    # Tier 3: Monthly (day 90 and older)
    effective = get_first_of_month(requested)
    return (effective, 'monthly')


def get_monday_of_week(d: date) -> date:
    """Get Monday of the week containing date d (Monday on or before d).

    Args:
        d: Any date

    Returns:
        The Monday of the ISO week containing d.
        Monday is weekday() == 0 in Python.
    """
    return d - timedelta(days=d.weekday())


def get_first_of_month(d: date) -> date:
    """Get the 1st day of the month containing date d.

    Args:
        d: Any date

    Returns:
        The 1st of the month (YYYY-MM-01).
    """
    return d.replace(day=1)


def get_required_daily_snapshots(
    today: Optional[date] = None,
    time_provider: Optional[TimeProvider] = None
) -> list[date]:
    """Get list of required daily snapshot dates in daily window.

    Args:
        today: Current date. If None, uses time_provider.
        time_provider: TimeProvider instance.

    Returns:
        List of dates within daily window, newest first (30 dates).
    """
    if today is None:
        today = get_today(time_provider)

    snapshots = []
    for i in range(DAILY_WINDOW_DAYS):
        snapshots.append(today - timedelta(days=i))

    return snapshots


def get_required_weekly_snapshots(
    today: Optional[date] = None,
    time_provider: Optional[TimeProvider] = None
) -> list[date]:
    """Get list of required weekly snapshot dates (Mondays) in weekly window.

    Returns Mondays in the range [today - 89 days, today - 30 days].

    Args:
        today: Current date. If None, uses time_provider.
        time_provider: TimeProvider instance.

    Returns:
        List of Monday dates within weekly window, newest first (~8-9 Mondays).
    """
    if today is None:
        today = get_today(time_provider)

    # Weekly window: day 30 to day 89
    weekly_start = today - timedelta(days=DAILY_WINDOW_DAYS)  # Day 30
    weekly_end = today - timedelta(days=DAILY_WINDOW_DAYS + WEEKLY_WINDOW_DAYS - 1)  # Day 89

    snapshots = []
    # Start from the Monday on or before weekly_start
    current = get_monday_of_week(weekly_start)

    while current >= weekly_end:
        # Only include if within the weekly window
        if current <= weekly_start:
            snapshots.append(current)
        current -= timedelta(days=7)

    return snapshots


def get_required_monthly_snapshots(
    today: Optional[date] = None,
    time_provider: Optional[TimeProvider] = None,
    limit: Optional[int] = None
) -> list[date]:
    """Get list of required monthly snapshot dates (1st of month) for history.

    Returns 1st-of-month dates from MONTHLY_START to before the weekly window.

    Args:
        today: Current date. If None, uses time_provider.
        time_provider: TimeProvider instance.
        limit: Optional limit on number of months to return (for backfill batching).

    Returns:
        List of 1st-of-month dates, newest first.
    """
    if today is None:
        today = get_today(time_provider)

    # Monthly window ends at day 90 (the day after weekly window ends)
    monthly_boundary = today - timedelta(days=DAILY_WINDOW_DAYS + WEEKLY_WINDOW_DAYS)

    snapshots = []
    current = get_first_of_month(monthly_boundary)

    count = 0
    while current >= MONTHLY_START:
        snapshots.append(current)
        count += 1
        if limit is not None and count >= limit:
            break
        # Move to previous month
        current = get_first_of_month(current - timedelta(days=1))

    return snapshots


def get_all_required_snapshots(
    today: Optional[date] = None,
    time_provider: Optional[TimeProvider] = None,
    include_monthly: bool = True,
    monthly_limit: Optional[int] = None
) -> list[tuple[date, CadenceType]]:
    """Get all required snapshot dates with their cadence type.

    Args:
        today: Current date. If None, uses time_provider.
        time_provider: TimeProvider instance.
        include_monthly: Whether to include monthly snapshots (for partial sync).
        monthly_limit: Limit on monthly snapshots to include.

    Returns:
        List of (date, cadence_type) tuples, newest first.
    """
    if today is None:
        today = get_today(time_provider)

    snapshots: list[tuple[date, CadenceType]] = []

    # Daily snapshots (last 30 days)
    for d in get_required_daily_snapshots(today):
        snapshots.append((d, 'daily'))

    # Weekly snapshots (days 31-90)
    for d in get_required_weekly_snapshots(today):
        snapshots.append((d, 'weekly'))

    # Monthly snapshots (before day 90)
    if include_monthly:
        for d in get_required_monthly_snapshots(today, limit=monthly_limit):
            snapshots.append((d, 'monthly'))

    return snapshots


def get_cadence_boundaries(
    today: Optional[date] = None,
    time_provider: Optional[TimeProvider] = None
) -> dict:
    """Get the boundary dates for each cadence tier.

    Useful for debugging and status reporting.

    Args:
        today: Current date. If None, uses time_provider.
        time_provider: TimeProvider instance.

    Returns:
        Dict with boundary information for each tier.
    """
    if today is None:
        today = get_today(time_provider)

    daily_start = today
    daily_end = today - timedelta(days=DAILY_WINDOW_DAYS - 1)

    weekly_start = today - timedelta(days=DAILY_WINDOW_DAYS)
    weekly_end = today - timedelta(days=DAILY_WINDOW_DAYS + WEEKLY_WINDOW_DAYS - 1)

    return {
        'today': today.isoformat(),
        'daily': {
            'start': daily_start.isoformat(),
            'end': daily_end.isoformat(),
            'days': DAILY_WINDOW_DAYS,
        },
        'weekly': {
            'start': weekly_start.isoformat(),
            'end': weekly_end.isoformat(),
            'days': WEEKLY_WINDOW_DAYS,
        },
        'monthly': {
            'start': weekly_end.isoformat(),  # Day after weekly ends
            'end': MONTHLY_START.isoformat(),
        },
    }
