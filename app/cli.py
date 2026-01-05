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


def register_cli(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(import_fx_csv_command)
    app.cli.add_command(import_metals_csv_command)
    app.cli.add_command(import_crypto_csv_command)
    app.cli.add_command(seed_all_command)
