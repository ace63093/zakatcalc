"""Flask CLI commands for database management and data import."""
import csv
import os
import click
from flask import current_app
from flask.cli import with_appcontext

from app.db import get_db, init_db, get_db_path


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the SQLite database with schema."""
    init_db()
    click.echo(f'Initialized database at {get_db_path()}')


@click.command('import-fx-csv')
@click.argument('csv_path', type=click.Path(exists=True))
@with_appcontext
def import_fx_csv_command(csv_path):
    """Import FX rates from CSV file.

    CSV format: date,currency,rate_to_usd,source
    Example: 2025-12-01,CAD,1.4052,seed
    """
    count = import_fx_csv(csv_path)
    click.echo(f'Imported {count} FX rate records from {csv_path}')


@click.command('import-metals-csv')
@click.argument('csv_path', type=click.Path(exists=True))
@with_appcontext
def import_metals_csv_command(csv_path):
    """Import metal prices from CSV file.

    CSV format: date,metal,price_per_gram_usd,source
    Example: 2025-12-01,gold,82.50,seed
    """
    count = import_metals_csv(csv_path)
    click.echo(f'Imported {count} metal price records from {csv_path}')


@click.command('import-crypto-csv')
@click.argument('csv_path', type=click.Path(exists=True))
@with_appcontext
def import_crypto_csv_command(csv_path):
    """Import crypto prices from CSV file.

    CSV format: date,symbol,name,price_usd,rank,source
    Example: 2025-12-01,BTC,Bitcoin,97500.00,1,seed
    """
    count = import_crypto_csv(csv_path)
    click.echo(f'Imported {count} crypto price records from {csv_path}')


@click.command('seed-all')
@with_appcontext
def seed_all_command():
    """Initialize DB and import all seed CSVs from data/seed/."""
    init_db()
    click.echo(f'Initialized database at {get_db_path()}')

    data_dir = current_app.config.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '..', 'data'))
    seed_dir = os.path.join(data_dir, 'seed')

    if not os.path.exists(seed_dir):
        click.echo(f'Seed directory not found: {seed_dir}')
        return

    # Import FX rates
    fx_path = os.path.join(seed_dir, 'fx_rates.csv')
    if os.path.exists(fx_path):
        count = import_fx_csv(fx_path)
        click.echo(f'Imported {count} FX rate records')
    else:
        click.echo('No fx_rates.csv found in seed directory')

    # Import metal prices
    metals_path = os.path.join(seed_dir, 'metal_prices.csv')
    if os.path.exists(metals_path):
        count = import_metals_csv(metals_path)
        click.echo(f'Imported {count} metal price records')
    else:
        click.echo('No metal_prices.csv found in seed directory')

    # Import crypto prices
    crypto_path = os.path.join(seed_dir, 'crypto_prices.csv')
    if os.path.exists(crypto_path):
        count = import_crypto_csv(crypto_path)
        click.echo(f'Imported {count} crypto price records')
    else:
        click.echo('No crypto_prices.csv found in seed directory')

    # Update meta
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
        ('last_seed', 'completed')
    )
    db.commit()
    click.echo('Seed complete!')


def import_fx_csv(csv_path: str) -> int:
    """Import FX rates from CSV file. Returns count of records imported."""
    db = get_db()
    count = 0

    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            db.execute('''
                INSERT OR REPLACE INTO fx_rates (date, currency, rate_to_usd, source)
                VALUES (?, ?, ?, ?)
            ''', (row['date'], row['currency'], float(row['rate_to_usd']), row.get('source', 'csv')))
            count += 1

    # Always ensure USD = 1.0 for each date
    db.execute('''
        INSERT OR REPLACE INTO fx_rates (date, currency, rate_to_usd, source)
        SELECT DISTINCT date, 'USD', 1.0, 'system'
        FROM fx_rates
        WHERE currency != 'USD'
    ''')

    db.commit()
    return count


def import_metals_csv(csv_path: str) -> int:
    """Import metal prices from CSV file. Returns count of records imported."""
    db = get_db()
    count = 0

    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            db.execute('''
                INSERT OR REPLACE INTO metal_prices (date, metal, price_per_gram_usd, source)
                VALUES (?, ?, ?, ?)
            ''', (row['date'], row['metal'].lower(), float(row['price_per_gram_usd']), row.get('source', 'csv')))
            count += 1

    db.commit()
    return count


def import_crypto_csv(csv_path: str) -> int:
    """Import crypto prices from CSV file. Returns count of records imported."""
    db = get_db()
    count = 0

    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row['rank']) if row.get('rank') else None
            db.execute('''
                INSERT OR REPLACE INTO crypto_prices (date, symbol, name, price_usd, rank, source)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (row['date'], row['symbol'].upper(), row['name'], float(row['price_usd']), rank, row.get('source', 'csv')))
            count += 1

    db.commit()
    return count


@click.command('mirror-to-r2')
@click.option('--cadence', default='daily', help='Cadence label (daily, weekly, monthly)')
@click.option('--limit', default=0, help='Max dates to mirror (0 = all)')
@with_appcontext
def mirror_to_r2_command(cadence, limit):
    """Mirror existing SQLite pricing data to R2.

    Reads all unique dates from SQLite and pushes FX, metals, and crypto
    snapshots to R2 for each date.
    """
    from app.services.r2_client import get_r2_client
    from app.services.r2_config import is_r2_enabled

    if not is_r2_enabled():
        click.echo('Error: R2 is not enabled. Set R2_ENABLED=1 and configure credentials.')
        return

    r2 = get_r2_client()
    if not r2:
        click.echo('Error: Could not create R2 client.')
        return

    db = get_db()

    # Get all unique dates with data
    fx_dates = db.execute('SELECT DISTINCT date FROM fx_rates ORDER BY date').fetchall()
    metal_dates = db.execute('SELECT DISTINCT date FROM metal_prices ORDER BY date').fetchall()
    crypto_dates = db.execute('SELECT DISTINCT date FROM crypto_prices ORDER BY date').fetchall()

    all_dates = sorted(set(
        [r['date'] for r in fx_dates] +
        [r['date'] for r in metal_dates] +
        [r['date'] for r in crypto_dates]
    ))

    if limit > 0:
        all_dates = all_dates[-limit:]  # Most recent N dates

    click.echo(f'Found {len(all_dates)} dates to mirror (cadence: {cadence})')

    fx_count = 0
    metals_count = 0
    crypto_count = 0

    for date_str in all_dates:
        # Mirror FX rates
        fx_rows = db.execute(
            'SELECT currency, rate_to_usd FROM fx_rates WHERE date = ?',
            (date_str,)
        ).fetchall()
        if fx_rows:
            fx_data = {row['currency']: row['rate_to_usd'] for row in fx_rows}
            try:
                from datetime import date as dt_date
                r2.put_snapshot('fx', cadence, dt_date.fromisoformat(date_str), {'data': fx_data})
                fx_count += 1
            except Exception as e:
                click.echo(f'  Error uploading FX {date_str}: {e}')

        # Mirror metal prices
        metal_rows = db.execute(
            'SELECT metal, price_per_gram_usd FROM metal_prices WHERE date = ?',
            (date_str,)
        ).fetchall()
        if metal_rows:
            metals_data = {row['metal']: row['price_per_gram_usd'] for row in metal_rows}
            try:
                from datetime import date as dt_date
                r2.put_snapshot('metals', cadence, dt_date.fromisoformat(date_str), {'data': metals_data})
                metals_count += 1
            except Exception as e:
                click.echo(f'  Error uploading metals {date_str}: {e}')

        # Mirror crypto prices
        crypto_rows = db.execute(
            'SELECT symbol, name, price_usd, rank FROM crypto_prices WHERE date = ?',
            (date_str,)
        ).fetchall()
        if crypto_rows:
            crypto_data = {
                row['symbol']: {
                    'name': row['name'],
                    'price': row['price_usd'],
                    'rank': row['rank']
                } for row in crypto_rows
            }
            try:
                from datetime import date as dt_date
                r2.put_snapshot('crypto', cadence, dt_date.fromisoformat(date_str), {'data': crypto_data})
                crypto_count += 1
            except Exception as e:
                click.echo(f'  Error uploading crypto {date_str}: {e}')

    click.echo(f'Mirrored to R2: {fx_count} FX, {metals_count} metals, {crypto_count} crypto snapshots')


@click.command('backfill-r2')
@click.option('--dry-run', is_flag=True, help='Show what would be uploaded without uploading')
@click.option('--monthly-limit', default=None, type=int, help='Max months of monthly snapshots')
@with_appcontext
def backfill_r2_command(dry_run, monthly_limit):
    """Backfill R2 with SQLite data using proper 3-tier cadence.

    For each required snapshot (daily/weekly/monthly), checks if R2 has it.
    If not, uploads from SQLite.
    """
    from datetime import date as dt_date
    from app.services.r2_client import get_r2_client
    from app.services.r2_config import is_r2_enabled
    from app.services.cadence import get_all_required_snapshots
    from app.services.time_provider import get_today

    if not is_r2_enabled():
        click.echo('Error: R2 is not enabled. Set R2_ENABLED=1 and configure credentials.')
        return

    r2 = get_r2_client()
    if not r2:
        click.echo('Error: Could not create R2 client.')
        return

    db = get_db()
    today = get_today()

    # Get required snapshots using cadence system
    required = get_all_required_snapshots(
        today=today,
        include_monthly=True,
        monthly_limit=monthly_limit
    )

    click.echo(f'Checking {len(required)} required snapshots...')

    missing_fx = 0
    missing_metals = 0
    missing_crypto = 0
    uploaded_fx = 0
    uploaded_metals = 0
    uploaded_crypto = 0

    for snapshot_date, cadence in required:
        date_str = snapshot_date.isoformat()

        # Check FX
        fx_rows = db.execute(
            'SELECT currency, rate_to_usd FROM fx_rates WHERE date = ?',
            (date_str,)
        ).fetchall()
        if fx_rows:
            try:
                if not r2.has_snapshot('fx', cadence, snapshot_date):
                    missing_fx += 1
                    if not dry_run:
                        fx_data = {row['currency']: row['rate_to_usd'] for row in fx_rows}
                        r2.put_snapshot('fx', cadence, snapshot_date, {
                            'source': 'cli-backfill',
                            'data': fx_data,
                        })
                        uploaded_fx += 1
                        click.echo(f'  Uploaded FX {date_str} ({cadence})')
            except Exception as e:
                click.echo(f'  Error checking/uploading FX {date_str}: {e}')

        # Check metals
        metal_rows = db.execute(
            'SELECT metal, price_per_gram_usd FROM metal_prices WHERE date = ?',
            (date_str,)
        ).fetchall()
        if metal_rows:
            try:
                if not r2.has_snapshot('metals', cadence, snapshot_date):
                    missing_metals += 1
                    if not dry_run:
                        metals_data = {row['metal']: row['price_per_gram_usd'] for row in metal_rows}
                        r2.put_snapshot('metals', cadence, snapshot_date, {
                            'source': 'cli-backfill',
                            'data': metals_data,
                        })
                        uploaded_metals += 1
                        click.echo(f'  Uploaded metals {date_str} ({cadence})')
            except Exception as e:
                click.echo(f'  Error checking/uploading metals {date_str}: {e}')

        # Check crypto
        crypto_rows = db.execute(
            'SELECT symbol, name, price_usd, rank FROM crypto_prices WHERE date = ?',
            (date_str,)
        ).fetchall()
        if crypto_rows:
            try:
                if not r2.has_snapshot('crypto', cadence, snapshot_date):
                    missing_crypto += 1
                    if not dry_run:
                        crypto_data = {
                            row['symbol']: {
                                'name': row['name'],
                                'price': row['price_usd'],
                                'rank': row['rank'],
                            }
                            for row in crypto_rows
                        }
                        r2.put_snapshot('crypto', cadence, snapshot_date, {
                            'source': 'cli-backfill',
                            'data': crypto_data,
                        })
                        uploaded_crypto += 1
                        click.echo(f'  Uploaded crypto {date_str} ({cadence})')
            except Exception as e:
                click.echo(f'  Error checking/uploading crypto {date_str}: {e}')

    if dry_run:
        click.echo(f'\nDry run - would upload: {missing_fx} FX, {missing_metals} metals, {missing_crypto} crypto')
    else:
        click.echo(f'\nBackfill complete: {uploaded_fx} FX, {uploaded_metals} metals, {uploaded_crypto} crypto uploaded')


@click.command('sync-prices')
@click.option('--start', 'start_date', default=None, help='Start date (YYYY-MM-DD). Defaults to today.')
@click.option('--end', 'end_date', default=None, help='End date (YYYY-MM-DD). Defaults to start date.')
@click.option('--types', default=None, help='Comma-separated types to sync: fx,metals,crypto. Defaults to all.')
@with_appcontext
def sync_prices_command(start_date, end_date, types):
    """Sync pricing data from upstream providers.

    Examples:
        flask sync-prices                          # Sync today
        flask sync-prices --start 2026-01-27       # Sync single date
        flask sync-prices --start 2026-01-27 --end 2026-01-31  # Sync range
        flask sync-prices --types fx,metals        # Sync only FX and metals
    """
    from datetime import date, timedelta
    from app.services.config import is_sync_enabled
    from app.services.sync import get_sync_service

    if not is_sync_enabled():
        click.echo('Error: Network sync is disabled. Set PRICING_ALLOW_NETWORK=1')
        return

    # Parse dates
    today = date.today()
    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError:
            click.echo(f'Error: Invalid start date format: {start_date}. Use YYYY-MM-DD.')
            return
    else:
        start = today

    if end_date:
        try:
            end = date.fromisoformat(end_date)
        except ValueError:
            click.echo(f'Error: Invalid end date format: {end_date}. Use YYYY-MM-DD.')
            return
    else:
        end = start

    if end < start:
        click.echo('Error: End date must be >= start date.')
        return

    # Parse types
    type_list = None
    if types:
        type_list = [t.strip() for t in types.split(',')]
        valid_types = {'fx', 'metals', 'crypto'}
        invalid = set(type_list) - valid_types
        if invalid:
            click.echo(f'Error: Invalid types: {invalid}. Valid: fx, metals, crypto')
            return

    # Perform sync
    sync_service = get_sync_service()
    num_days = (end - start).days + 1

    click.echo(f'Syncing {num_days} day(s) from {start} to {end}...')
    if type_list:
        click.echo(f'Types: {", ".join(type_list)}')

    current = start
    success_count = 0
    error_count = 0

    while current <= end:
        result = sync_service.sync_date(current, type_list)
        if result.get('success'):
            success_count += 1
            click.echo(f'  {current}: OK')
        else:
            error_count += 1
            results = result.get('results', {})
            errors = [f"{k}: {v.get('error', 'failed')}" for k, v in results.items() if v.get('status') != 'success']
            click.echo(f'  {current}: FAILED - {"; ".join(errors) if errors else "unknown error"}')
        current += timedelta(days=1)

    click.echo(f'\nSync complete: {success_count} succeeded, {error_count} failed')


def register_cli(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(import_fx_csv_command)
    app.cli.add_command(import_metals_csv_command)
    app.cli.add_command(import_crypto_csv_command)
    app.cli.add_command(seed_all_command)
    app.cli.add_command(mirror_to_r2_command)
    app.cli.add_command(backfill_r2_command)
    app.cli.add_command(sync_prices_command)
