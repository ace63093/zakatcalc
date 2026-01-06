"""Tests for 3-tier snapshot cadence calculation.

This module tests the cadence algorithm that maps requested dates to
effective snapshot dates:
- Daily: last 30 days (days 0-29)
- Weekly: days 30-89 (Mondays)
- Monthly: day 90+ (1st of month)
"""
import pytest
from datetime import date, timedelta

from app.services.cadence import (
    get_effective_snapshot_date,
    get_monday_of_week,
    get_first_of_month,
    get_required_daily_snapshots,
    get_required_weekly_snapshots,
    get_required_monthly_snapshots,
    get_all_required_snapshots,
    DAILY_WINDOW_DAYS,
    WEEKLY_WINDOW_DAYS,
    MONTHLY_START,
)
from app.services.time_provider import TimeProvider


class TestBoundaryConstants:
    """Verify boundary constants are correctly defined."""

    def test_daily_window_is_30_days(self):
        assert DAILY_WINDOW_DAYS == 30

    def test_weekly_window_is_60_days(self):
        assert WEEKLY_WINDOW_DAYS == 60

    def test_monthly_start_is_2000(self):
        assert MONTHLY_START == date(2000, 1, 1)


class TestGetMondayOfWeek:
    """Tests for get_monday_of_week helper."""

    def test_monday_returns_same_day(self):
        """Monday returns itself."""
        monday = date(2026, 1, 5)  # Monday
        assert get_monday_of_week(monday) == monday

    def test_wednesday_returns_monday(self):
        """Wednesday returns previous Monday."""
        wednesday = date(2026, 1, 7)  # Wednesday
        expected = date(2026, 1, 5)  # Monday
        assert get_monday_of_week(wednesday) == expected

    def test_sunday_returns_monday(self):
        """Sunday returns Monday of same week."""
        sunday = date(2026, 1, 11)  # Sunday
        expected = date(2026, 1, 5)  # Monday
        assert get_monday_of_week(sunday) == expected


class TestGetFirstOfMonth:
    """Tests for get_first_of_month helper."""

    def test_first_returns_same_day(self):
        """1st of month returns itself."""
        first = date(2026, 1, 1)
        assert get_first_of_month(first) == first

    def test_mid_month_returns_first(self):
        """Mid-month returns 1st."""
        mid = date(2026, 1, 15)
        expected = date(2026, 1, 1)
        assert get_first_of_month(mid) == expected

    def test_last_day_returns_first(self):
        """Last day of month returns 1st."""
        last = date(2026, 1, 31)
        expected = date(2026, 1, 1)
        assert get_first_of_month(last) == expected


class TestGetEffectiveSnapshotDate:
    """Tests for main 3-tier cadence algorithm."""

    def test_today_uses_daily_cadence(self, frozen_time, frozen_today):
        """Today's date uses daily cadence."""
        effective, cadence = get_effective_snapshot_date(frozen_today, today=frozen_today)
        assert cadence == 'daily'
        assert effective == frozen_today

    def test_day_10_uses_daily_cadence(self, frozen_time, frozen_today):
        """Day 10 (within daily window) uses daily cadence."""
        day_10 = frozen_today - timedelta(days=10)
        effective, cadence = get_effective_snapshot_date(day_10, today=frozen_today)
        assert cadence == 'daily'
        assert effective == day_10  # No mapping for daily

    def test_day_29_uses_daily_cadence(self, frozen_time, frozen_today):
        """Day 29 (last day of daily window) uses daily cadence."""
        day_29 = frozen_today - timedelta(days=29)
        effective, cadence = get_effective_snapshot_date(day_29, today=frozen_today)
        assert cadence == 'daily'
        assert effective == day_29  # No mapping for daily

    def test_day_30_uses_weekly_cadence(self, frozen_time, frozen_today):
        """Day 30 (first day of weekly window) uses weekly cadence."""
        day_30 = frozen_today - timedelta(days=30)
        effective, cadence = get_effective_snapshot_date(day_30, today=frozen_today)
        assert cadence == 'weekly'
        assert effective.weekday() == 0  # Must be Monday
        assert effective <= day_30  # Monday on or before

    def test_day_45_uses_weekly_cadence(self, frozen_time, frozen_today):
        """Day 45 (middle of weekly window) uses weekly cadence."""
        day_45 = frozen_today - timedelta(days=45)
        effective, cadence = get_effective_snapshot_date(day_45, today=frozen_today)
        assert cadence == 'weekly'
        assert effective.weekday() == 0  # Must be Monday
        assert effective <= day_45  # Monday on or before

    def test_day_89_uses_weekly_cadence(self, frozen_time, frozen_today):
        """Day 89 (last day of weekly window) uses weekly cadence."""
        day_89 = frozen_today - timedelta(days=89)
        effective, cadence = get_effective_snapshot_date(day_89, today=frozen_today)
        assert cadence == 'weekly'
        assert effective.weekday() == 0  # Must be Monday

    def test_day_90_uses_monthly_cadence(self, frozen_time, frozen_today):
        """Day 90 (first day of monthly window) uses monthly cadence."""
        day_90 = frozen_today - timedelta(days=90)
        effective, cadence = get_effective_snapshot_date(day_90, today=frozen_today)
        assert cadence == 'monthly'
        assert effective.day == 1  # Must be 1st of month
        assert effective <= day_90  # 1st on or before

    def test_day_180_uses_monthly_cadence(self, frozen_time, frozen_today):
        """Day 180 (~6 months ago) uses monthly cadence."""
        day_180 = frozen_today - timedelta(days=180)
        effective, cadence = get_effective_snapshot_date(day_180, today=frozen_today)
        assert cadence == 'monthly'
        assert effective.day == 1
        assert effective <= day_180

    def test_ancient_date_uses_monthly(self, frozen_time, frozen_today):
        """Very old date uses monthly cadence."""
        ancient = date(2010, 6, 15)
        effective, cadence = get_effective_snapshot_date(ancient, today=frozen_today)
        assert cadence == 'monthly'
        assert effective == date(2010, 6, 1)

    def test_before_monthly_start_clamps(self, frozen_time, frozen_today):
        """Dates before 2000-01-01 clamp to MONTHLY_START."""
        ancient = date(1999, 12, 31)
        effective, cadence = get_effective_snapshot_date(ancient, today=frozen_today)
        assert cadence == 'monthly'
        assert effective == MONTHLY_START

    def test_future_date_uses_today(self, frozen_time, frozen_today):
        """Future dates are treated as today."""
        future = frozen_today + timedelta(days=10)
        effective, cadence = get_effective_snapshot_date(future, today=frozen_today)
        assert cadence == 'daily'
        assert effective == frozen_today

    def test_daily_returns_same_date(self, frozen_time, frozen_today):
        """Daily cadence returns the requested date unchanged."""
        for days_ago in [0, 5, 15, 29]:
            requested = frozen_today - timedelta(days=days_ago)
            effective, cadence = get_effective_snapshot_date(requested, today=frozen_today)
            assert cadence == 'daily'
            assert effective == requested, f"Day {days_ago} should map to itself"

    def test_weekly_returns_monday(self, frozen_time, frozen_today):
        """Weekly cadence returns the Monday on or before requested."""
        # Test various days in weekly window
        for days_ago in [35, 50, 75, 85]:
            requested = frozen_today - timedelta(days=days_ago)
            effective, cadence = get_effective_snapshot_date(requested, today=frozen_today)
            assert cadence == 'weekly'
            assert effective.weekday() == 0, f"Day {days_ago} should map to Monday"
            assert effective <= requested, f"Monday should be on or before requested"

    def test_monthly_returns_first(self, frozen_time, frozen_today):
        """Monthly cadence returns the 1st of the month on or before requested."""
        for days_ago in [100, 150, 365]:
            requested = frozen_today - timedelta(days=days_ago)
            effective, cadence = get_effective_snapshot_date(requested, today=frozen_today)
            assert cadence == 'monthly'
            assert effective.day == 1, f"Day {days_ago} should map to 1st"
            assert effective <= requested, f"1st should be on or before requested"


class TestRequiredDailySnapshots:
    """Tests for daily snapshot list generation."""

    def test_returns_30_dates(self, frozen_time, frozen_today):
        """Returns exactly 30 daily snapshots."""
        snapshots = get_required_daily_snapshots(today=frozen_today)
        assert len(snapshots) == 30

    def test_newest_first(self, frozen_time, frozen_today):
        """Snapshots are ordered newest first."""
        snapshots = get_required_daily_snapshots(today=frozen_today)
        assert snapshots[0] == frozen_today
        for i in range(len(snapshots) - 1):
            assert snapshots[i] > snapshots[i + 1]

    def test_all_within_window(self, frozen_time, frozen_today):
        """All dates are within the 30-day window."""
        snapshots = get_required_daily_snapshots(today=frozen_today)
        oldest_allowed = frozen_today - timedelta(days=29)
        for d in snapshots:
            assert d >= oldest_allowed
            assert d <= frozen_today

    def test_includes_boundary_dates(self, frozen_time, frozen_today):
        """Includes both today and day 29."""
        snapshots = get_required_daily_snapshots(today=frozen_today)
        day_29 = frozen_today - timedelta(days=29)
        assert frozen_today in snapshots
        assert day_29 in snapshots


class TestRequiredWeeklySnapshots:
    """Tests for weekly snapshot list generation."""

    def test_returns_mondays(self, frozen_time, frozen_today):
        """All returned dates are Mondays."""
        snapshots = get_required_weekly_snapshots(today=frozen_today)
        for d in snapshots:
            assert d.weekday() == 0, f"{d} is not a Monday"

    def test_expected_count(self, frozen_time, frozen_today):
        """Returns approximately 8-9 Mondays for 60-day window."""
        snapshots = get_required_weekly_snapshots(today=frozen_today)
        # 60 days / 7 = ~8-9 weeks
        assert 8 <= len(snapshots) <= 10

    def test_within_weekly_window(self, frozen_time, frozen_today):
        """All Mondays are within the weekly window (days 30-89)."""
        snapshots = get_required_weekly_snapshots(today=frozen_today)
        # Weekly window: day 30 to day 89
        daily_boundary = frozen_today - timedelta(days=DAILY_WINDOW_DAYS - 1)  # day 29
        weekly_boundary = frozen_today - timedelta(days=DAILY_WINDOW_DAYS + WEEKLY_WINDOW_DAYS)  # day 90

        for d in snapshots:
            assert d < daily_boundary, f"{d} is in daily range"
            assert d >= weekly_boundary, f"{d} is in monthly range"

    def test_newest_first(self, frozen_time, frozen_today):
        """Snapshots are ordered newest first."""
        snapshots = get_required_weekly_snapshots(today=frozen_today)
        for i in range(len(snapshots) - 1):
            assert snapshots[i] > snapshots[i + 1]


class TestRequiredMonthlySnapshots:
    """Tests for monthly snapshot list generation."""

    def test_returns_first_of_month(self, frozen_time, frozen_today):
        """All returned dates are 1st of month."""
        snapshots = get_required_monthly_snapshots(today=frozen_today)
        for d in snapshots:
            assert d.day == 1, f"{d} is not 1st of month"

    def test_starts_after_weekly_window(self, frozen_time, frozen_today):
        """All months are before the weekly window."""
        snapshots = get_required_monthly_snapshots(today=frozen_today)
        weekly_boundary = frozen_today - timedelta(days=DAILY_WINDOW_DAYS + WEEKLY_WINDOW_DAYS)

        for d in snapshots:
            assert d < weekly_boundary, f"{d} is within weekly range"

    def test_ends_at_monthly_start(self, frozen_time, frozen_today):
        """Oldest snapshot is >= MONTHLY_START."""
        snapshots = get_required_monthly_snapshots(today=frozen_today)
        if snapshots:
            assert snapshots[-1] >= MONTHLY_START

    def test_limit_parameter(self, frozen_time, frozen_today):
        """Limit parameter restricts number of months returned."""
        snapshots = get_required_monthly_snapshots(today=frozen_today, limit=5)
        assert len(snapshots) == 5


class TestGetAllRequiredSnapshots:
    """Tests for combined snapshot list."""

    def test_includes_all_three_types(self, frozen_time, frozen_today):
        """Returns daily, weekly, and monthly snapshots."""
        snapshots = get_all_required_snapshots(today=frozen_today, monthly_limit=5)
        cadences = set(s[1] for s in snapshots)
        assert 'daily' in cadences
        assert 'weekly' in cadences
        assert 'monthly' in cadences

    def test_no_duplicate_dates(self, frozen_time, frozen_today):
        """No date appears twice."""
        snapshots = get_all_required_snapshots(today=frozen_today, monthly_limit=5)
        dates = [s[0] for s in snapshots]
        assert len(dates) == len(set(dates)), "Duplicate dates found"

    def test_tuple_format(self, frozen_time, frozen_today):
        """Each snapshot is (date, cadence_type) tuple."""
        snapshots = get_all_required_snapshots(today=frozen_today, monthly_limit=5)
        for snapshot in snapshots:
            assert isinstance(snapshot, tuple)
            assert len(snapshot) == 2
            assert isinstance(snapshot[0], date)
            assert snapshot[1] in ('daily', 'weekly', 'monthly')

    def test_include_monthly_false(self, frozen_time, frozen_today):
        """Can exclude monthly snapshots."""
        snapshots = get_all_required_snapshots(today=frozen_today, include_monthly=False)
        cadences = set(s[1] for s in snapshots)
        assert 'daily' in cadences
        assert 'weekly' in cadences
        assert 'monthly' not in cadences


class TestTimeProviderIntegration:
    """Tests for TimeProvider integration with cadence functions."""

    def test_uses_frozen_provider(self, frozen_time, frozen_today):
        """Cadence functions use the frozen TimeProvider."""
        # When TimeProvider is set as default, functions should use it
        effective, cadence = get_effective_snapshot_date(frozen_today)
        assert cadence == 'daily'
        assert effective == frozen_today

    def test_daily_snapshots_use_provider(self, frozen_time, frozen_today):
        """get_required_daily_snapshots uses TimeProvider."""
        snapshots = get_required_daily_snapshots()
        assert snapshots[0] == frozen_today

    def test_explicit_today_overrides_provider(self, frozen_time, frozen_today):
        """Explicit today parameter overrides TimeProvider."""
        different_today = date(2025, 6, 15)
        snapshots = get_required_daily_snapshots(today=different_today)
        assert snapshots[0] == different_today
