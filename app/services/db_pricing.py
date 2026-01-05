"""SQLite-backed pricing data queries with effective date fallback."""
from app.db import get_db


def get_fx_snapshot(date: str, base_currency: str = 'USD') -> tuple[str | None, dict]:
    """Get FX rates for a date with fallback to most recent prior date.

    Args:
        date: Requested date in YYYY-MM-DD format
        base_currency: Target base currency for cross-rates (default: USD)

    Returns:
        Tuple of (effective_date, fx_rates_dict) where fx_rates_dict
        has currency codes as keys and rates to base_currency as values.
        Returns (None, {}) if no data available.
    """
    db = get_db()

    # Find effective date (most recent date <= requested date)
    row = db.execute(
        'SELECT MAX(date) as effective_date FROM fx_rates WHERE date <= ?',
        (date,)
    ).fetchone()

    effective_date = row['effective_date'] if row else None
    if not effective_date:
        return (None, {})

    # Get all rates for effective date (stored as USD base)
    rows = db.execute(
        'SELECT currency, rate_to_usd FROM fx_rates WHERE date = ?',
        (effective_date,)
    ).fetchall()

    if not rows:
        return (None, {})

    # Build USD-based rates dict
    usd_rates = {row['currency']: row['rate_to_usd'] for row in rows}
    usd_rates['USD'] = 1.0  # Ensure USD is always present

    # Convert to requested base currency
    fx_rates = compute_cross_rates(usd_rates, base_currency)

    return (effective_date, fx_rates)


def get_metal_snapshot(date: str, base_currency: str = 'USD') -> tuple[str | None, dict]:
    """Get metal prices for a date with fallback.

    Args:
        date: Requested date in YYYY-MM-DD format
        base_currency: Target currency for prices (default: USD)

    Returns:
        Tuple of (effective_date, metals_dict) where metals_dict has
        metal names as keys and price_per_gram in base_currency as values.
    """
    db = get_db()

    # Find effective date
    row = db.execute(
        'SELECT MAX(date) as effective_date FROM metal_prices WHERE date <= ?',
        (date,)
    ).fetchone()

    effective_date = row['effective_date'] if row else None
    if not effective_date:
        return (None, {})

    # Get metal prices in USD
    rows = db.execute(
        'SELECT metal, price_per_gram_usd FROM metal_prices WHERE date = ?',
        (effective_date,)
    ).fetchall()

    if not rows:
        return (None, {})

    # Get FX rate to convert USD to base_currency
    _, fx_rates = get_fx_snapshot(date, base_currency)
    usd_to_base = fx_rates.get('USD', 1.0) if fx_rates else 1.0

    # Convert prices to base currency
    metals = {}
    for row in rows:
        price_in_base = row['price_per_gram_usd'] * usd_to_base
        metals[row['metal']] = round(price_in_base, 4)

    return (effective_date, metals)


def get_crypto_snapshot(date: str, base_currency: str = 'USD', symbols: list | None = None) -> tuple[str | None, dict]:
    """Get crypto prices for a date with fallback.

    Args:
        date: Requested date in YYYY-MM-DD format
        base_currency: Target currency for prices (default: USD)
        symbols: Optional list of symbols to filter (None = all available)

    Returns:
        Tuple of (effective_date, crypto_dict) where crypto_dict has
        symbols as keys and dicts with name, price, rank as values.
    """
    db = get_db()

    # Find effective date
    row = db.execute(
        'SELECT MAX(date) as effective_date FROM crypto_prices WHERE date <= ?',
        (date,)
    ).fetchone()

    effective_date = row['effective_date'] if row else None
    if not effective_date:
        return (None, {})

    # Build query with optional symbol filter
    if symbols:
        placeholders = ','.join('?' * len(symbols))
        query = f'SELECT symbol, name, price_usd, rank FROM crypto_prices WHERE date = ? AND symbol IN ({placeholders}) ORDER BY rank'
        rows = db.execute(query, [effective_date] + [s.upper() for s in symbols]).fetchall()
    else:
        rows = db.execute(
            'SELECT symbol, name, price_usd, rank FROM crypto_prices WHERE date = ? ORDER BY rank',
            (effective_date,)
        ).fetchall()

    if not rows:
        return (None, {})

    # Get FX rate to convert USD to base_currency
    _, fx_rates = get_fx_snapshot(date, base_currency)
    usd_to_base = fx_rates.get('USD', 1.0) if fx_rates else 1.0

    # Convert prices to base currency
    crypto = {}
    for row in rows:
        price_in_base = row['price_usd'] * usd_to_base
        crypto[row['symbol']] = {
            'name': row['name'],
            'price': round(price_in_base, 2),
            'rank': row['rank']
        }

    return (effective_date, crypto)


def get_available_date_range() -> tuple[str | None, str | None]:
    """Get the min and max dates available in the database.

    Returns:
        Tuple of (min_date, max_date) or (None, None) if no data.
    """
    db = get_db()

    # Get range from each table
    fx_range = db.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM fx_rates').fetchone()
    metal_range = db.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM metal_prices').fetchone()
    crypto_range = db.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM crypto_prices').fetchone()

    # Find overall min/max
    dates = []
    for row in [fx_range, metal_range, crypto_range]:
        if row['min_date']:
            dates.append(row['min_date'])
        if row['max_date']:
            dates.append(row['max_date'])

    if not dates:
        return (None, None)

    return (min(dates), max(dates))


def compute_cross_rates(usd_rates: dict, base_currency: str) -> dict:
    """Compute cross rates from USD-based rates to a different base.

    Formula: If 1 USD = X target_currency, and 1 USD = Y base_currency,
    then 1 base_currency = X/Y target_currency.

    But we want: how many base_currency units for 1 target_currency?
    Answer: Y/X

    However, for display we typically want:
    - fx_rates[base_currency] = 1.0
    - fx_rates[other] = how many base_currency per 1 other_currency

    Actually for conversion from other to base:
    amount_in_base = amount_in_other * rate
    rate = usd_rate_of_base / usd_rate_of_other

    Args:
        usd_rates: Dict of currency -> rate_to_usd (1 USD = X currency)
        base_currency: Target base currency

    Returns:
        Dict of currency -> rate where rate is the conversion factor
        to convert from that currency to base_currency.
    """
    base_rate = usd_rates.get(base_currency, 1.0)

    result = {}
    for currency, usd_rate in usd_rates.items():
        if usd_rate == 0:
            result[currency] = 0.0
        else:
            # To convert X currency to base:
            # 1. X currency = X/usd_rate USD
            # 2. X/usd_rate USD = (X/usd_rate) * base_rate base_currency
            # So rate = base_rate / usd_rate
            result[currency] = round(base_rate / usd_rate, 6)

    return result


def get_coverage_flags(date: str) -> dict:
    """Check what data is available for a given date.

    Returns:
        Dict with coverage information for each data type.
    """
    db = get_db()

    # Check FX
    fx_row = db.execute('SELECT MAX(date) as effective FROM fx_rates WHERE date <= ?', (date,)).fetchone()
    fx_exact = db.execute('SELECT COUNT(*) as cnt FROM fx_rates WHERE date = ?', (date,)).fetchone()

    # Check metals
    metal_row = db.execute('SELECT MAX(date) as effective FROM metal_prices WHERE date <= ?', (date,)).fetchone()
    metal_exact = db.execute('SELECT COUNT(*) as cnt FROM metal_prices WHERE date = ?', (date,)).fetchone()

    # Check crypto
    crypto_row = db.execute('SELECT MAX(date) as effective FROM crypto_prices WHERE date <= ?', (date,)).fetchone()
    crypto_exact = db.execute('SELECT COUNT(*) as cnt FROM crypto_prices WHERE date = ?', (date,)).fetchone()

    return {
        'fx_available': fx_row['effective'] is not None,
        'fx_date_exact': fx_exact['cnt'] > 0,
        'fx_effective_date': fx_row['effective'],
        'metals_available': metal_row['effective'] is not None,
        'metals_date_exact': metal_exact['cnt'] > 0,
        'metals_effective_date': metal_row['effective'],
        'crypto_available': crypto_row['effective'] is not None,
        'crypto_date_exact': crypto_exact['cnt'] > 0,
        'crypto_effective_date': crypto_row['effective'],
    }
