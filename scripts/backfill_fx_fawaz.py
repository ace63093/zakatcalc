#!/usr/bin/env python3
"""One-time FX backfill using fawazahmed0/exchange-api.

Backfills FX rates (USD base) into SQLite and mirrors to R2 using the same
schema/format as the existing sync flow. Intended for historical backfill
(e.g., all dates in 2025 and earlier).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from typing import Iterable

from app.db import get_schema
from app.services.providers.fx_providers import FawazExchangeAPIProvider
from app.services.r2_client import get_r2_client
from app.services.r2_config import is_r2_enabled

DEFAULT_START = date(2000, 1, 1)
DEFAULT_END = date(2025, 12, 31)
EPSILON = 1e-9


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}") from exc


def iter_daily(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def iter_monthly(start: date, end: date) -> Iterable[date]:
    current = start.replace(day=1)
    while current <= end:
        yield current
        year = current.year + (current.month // 12)
        month = (current.month % 12) + 1
        current = date(year, month, 1)


def ensure_schema(conn: sqlite3.Connection) -> None:
    try:
        conn.execute('SELECT 1 FROM fx_rates LIMIT 1')
    except sqlite3.OperationalError:
        conn.executescript(get_schema())
        conn.commit()


def load_existing_rates(conn: sqlite3.Connection, date_str: str) -> dict[str, float]:
    rows = conn.execute(
        'SELECT currency, rate_to_usd FROM fx_rates WHERE date = ?',
        (date_str,)
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def has_diff(existing: dict[str, float], incoming: dict[str, float]) -> bool:
    if not existing:
        return True

    if set(existing.keys()) != set(incoming.keys()):
        return True

    for currency, rate in incoming.items():
        current = existing.get(currency)
        if current is None:
            return True
        if abs(current - rate) > EPSILON:
            return True

    return False


def write_rates(
    conn: sqlite3.Connection,
    target_date: date,
    rates: dict[str, float],
    source: str,
    snapshot_type: str,
) -> None:
    date_str = target_date.isoformat()
    conn.execute('DELETE FROM fx_rates WHERE date = ?', (date_str,))
    conn.executemany(
        '''
        INSERT OR REPLACE INTO fx_rates (date, currency, rate_to_usd, source, snapshot_type)
        VALUES (?, ?, ?, ?, ?)
        ''',
        [
            (date_str, currency, rate, source, snapshot_type)
            for currency, rate in rates.items()
        ]
    )
    conn.execute(
        '''
        INSERT INTO sync_log (sync_date, data_type, provider, status, records_count, error_message, snapshot_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (date_str, 'fx', source, 'success', len(rates), None, snapshot_type)
    )
    conn.commit()


def mirror_to_r2(r2, snapshot_type: str, target_date: date, rates: dict[str, float], source: str) -> None:
    if not r2:
        return
    r2.put_snapshot('fx', snapshot_type, target_date, {
        'source': source,
        'data': rates,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill FX rates using fawaz exchange API.')
    parser.add_argument('--start', type=parse_date, default=DEFAULT_START)
    parser.add_argument('--end', type=parse_date, default=DEFAULT_END)
    parser.add_argument('--daily', action='store_true', help='Backfill daily snapshots (default: monthly).')
    parser.add_argument('--sleep', type=float, default=0.0, help='Seconds to sleep between requests.')
    parser.add_argument('--dry-run', action='store_true', help='Fetch and diff but do not write.')

    args = parser.parse_args()

    start = args.start
    end = min(args.end, DEFAULT_END)
    if args.end > DEFAULT_END:
        print(f"Clamping end date to {DEFAULT_END.isoformat()} (requested {args.end.isoformat()}).")

    if start > end:
        print('Start date must be on or before end date.')
        return 2

    cadence = 'daily' if args.daily else 'monthly'
    iterator = iter_daily(start, end) if args.daily else iter_monthly(start, end)

    data_dir = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data'))
    db_path = os.path.join(os.path.abspath(data_dir), 'pricing.sqlite')

    conn = sqlite3.connect(db_path)
    ensure_schema(conn)

    provider = FawazExchangeAPIProvider()
    r2 = get_r2_client() if is_r2_enabled() else None

    processed = 0
    updated = 0
    skipped = 0
    errors = 0

    for target_date in iterator:
        date_str = target_date.isoformat()
        try:
            fx_rates = provider.get_rates(target_date)
            rates = {rate.currency: rate.rate_to_usd for rate in fx_rates}
            rates.setdefault('USD', 1.0)

            existing = load_existing_rates(conn, date_str)
            if not has_diff(existing, rates):
                skipped += 1
                processed += 1
                continue

            if not args.dry_run:
                write_rates(conn, target_date, rates, provider.name, cadence)
                mirror_to_r2(r2, cadence, target_date, rates, provider.name)

            updated += 1
            processed += 1

        except Exception as exc:
            errors += 1
            processed += 1
            print(f"Error {date_str}: {exc}")

        if args.sleep:
            time.sleep(args.sleep)

    conn.close()

    print(
        f"Done. processed={processed} updated={updated} skipped={skipped} "
        f"errors={errors} cadence={cadence} dry_run={args.dry_run}"
    )
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
