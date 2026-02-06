"""IP geolocation using Apple's CSV database.

Downloads Apple's static CSV mapping IP CIDR ranges to country/region/city.
Builds an in-memory binary-search index for O(log n) lookups.
Uses R2 as primary cache, SQLite as local mirror.

No new dependencies: ipaddress, bisect, hashlib are all stdlib.
"""
import bisect
import gzip
import hashlib
import ipaddress
import json
import logging
import sqlite3
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .config import get_visitor_hash_salt, is_geolocation_enabled

logger = logging.getLogger('geolocation')

APPLE_GEODB_URL = 'https://ip-geolocation.apple.com/'
R2_GEODB_KEY_SUFFIX = 'geolocation/apple_geodb.json.gz'


@dataclass
class GeoResult:
    country_code: str
    region_code: Optional[str] = None
    city: Optional[str] = None


def _parse_cidr(cidr_str: str):
    """Convert CIDR string to (start_hex, end_hex, ip_version).

    Returns zero-padded hex strings for sortable comparison.
    IPv4: 8 hex chars, IPv6: 32 hex chars.
    """
    network = ipaddress.ip_network(cidr_str, strict=False)
    start_int = int(network.network_address)
    end_int = int(network.broadcast_address)
    version = network.version

    if version == 4:
        pad = 8
    else:
        pad = 32

    start_hex = format(start_int, f'0{pad}x')
    end_hex = format(end_int, f'0{pad}x')
    return start_hex, end_hex, version


def _ip_to_hex(ip_str: str):
    """Convert IP address string to (hex_string, version)."""
    addr = ipaddress.ip_address(ip_str)
    version = addr.version
    if version == 4:
        pad = 8
    else:
        pad = 32
    return format(int(addr), f'0{pad}x'), version


class GeoIndex:
    """In-memory binary search index for IP geolocation."""

    def __init__(self):
        # Separate sorted arrays for IPv4 and IPv6
        # Each array: list of (start_hex, end_hex, country_code, region_code, city)
        self._v4_starts = []
        self._v4_entries = []
        self._v6_starts = []
        self._v6_entries = []

    def load_from_rows(self, rows):
        """Build index from parsed tuples.

        Args:
            rows: iterable of (ip_start, ip_end, cidr, country_code, region_code, city, ip_version)
        """
        v4 = []
        v6 = []
        for row in rows:
            ip_start, ip_end, cidr, country_code, region_code, city, ip_version = row
            entry = (ip_start, ip_end, country_code, region_code, city)
            if ip_version == 4:
                v4.append(entry)
            else:
                v6.append(entry)

        # Sort by start address
        v4.sort(key=lambda e: e[0])
        v6.sort(key=lambda e: e[0])

        self._v4_starts = [e[0] for e in v4]
        self._v4_entries = v4
        self._v6_starts = [e[0] for e in v6]
        self._v6_entries = v6

    @property
    def size(self):
        return len(self._v4_entries) + len(self._v6_entries)

    def lookup(self, ip_str: str) -> Optional[GeoResult]:
        """Look up IP address, return GeoResult or None."""
        try:
            ip_hex, version = _ip_to_hex(ip_str)
        except (ValueError, TypeError):
            return None

        if version == 4:
            starts = self._v4_starts
            entries = self._v4_entries
        else:
            starts = self._v6_starts
            entries = self._v6_entries

        if not starts:
            return None

        # Find the rightmost entry whose start <= ip_hex
        idx = bisect.bisect_right(starts, ip_hex) - 1
        if idx < 0:
            return None

        entry = entries[idx]
        start_hex, end_hex, country_code, region_code, city = entry

        # Check if IP falls within this range
        if start_hex <= ip_hex <= end_hex:
            return GeoResult(
                country_code=country_code,
                region_code=region_code or None,
                city=city or None,
            )

        return None


# Module-level singleton
_geo_index: Optional[GeoIndex] = None


def get_geo_index() -> Optional[GeoIndex]:
    """Get the module-level GeoIndex singleton."""
    return _geo_index


def set_geo_index(index: Optional[GeoIndex]):
    """Set the module-level GeoIndex singleton."""
    global _geo_index
    _geo_index = index


def download_and_parse_apple_geodb():
    """Download Apple's CSV geodb and parse into rows.

    Returns:
        list of (ip_start, ip_end, cidr, country_code, region_code, city, ip_version)
    """
    from .config import get_user_agent
    req = urllib.request.Request(
        APPLE_GEODB_URL,
        headers={'User-Agent': get_user_agent()},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode('utf-8')

    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split(',')
        if len(parts) < 2:
            continue

        cidr_str = parts[0].strip()
        country_code = parts[1].strip()
        region_code = parts[2].strip() if len(parts) > 2 else ''
        city = parts[3].strip() if len(parts) > 3 else ''

        try:
            start_hex, end_hex, version = _parse_cidr(cidr_str)
        except (ValueError, TypeError):
            logger.debug(f"Skipping invalid CIDR: {cidr_str}")
            continue

        rows.append((start_hex, end_hex, cidr_str, country_code, region_code, city, version))

    logger.info(f"Parsed {len(rows)} CIDR entries from Apple geodb")
    return rows


def store_geodb_to_sqlite(db, rows):
    """Store parsed geodb rows to SQLite, replacing existing data.

    Args:
        db: sqlite3.Connection
        rows: list of (ip_start, ip_end, cidr, country_code, region_code, city, ip_version)
    """
    db.execute('DELETE FROM ip_geolocation')
    db.executemany(
        'INSERT INTO ip_geolocation (ip_start, ip_end, cidr, country_code, region_code, city, ip_version) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        rows,
    )
    db.execute(
        "INSERT OR REPLACE INTO meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
        ('geodb_last_updated', 'completed'),
    )
    db.commit()
    logger.info(f"Stored {len(rows)} geodb entries to SQLite")


def load_geodb_from_sqlite(db):
    """Load all geodb rows from SQLite.

    Returns:
        list of (ip_start, ip_end, cidr, country_code, region_code, city, ip_version)
    """
    cursor = db.execute(
        'SELECT ip_start, ip_end, cidr, country_code, region_code, city, ip_version '
        'FROM ip_geolocation'
    )
    rows = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in cursor.fetchall()]
    logger.info(f"Loaded {len(rows)} geodb entries from SQLite")
    return rows


def get_geodb_last_updated(db) -> Optional[str]:
    """Check meta table for geodb last update timestamp."""
    cursor = db.execute("SELECT updated_at FROM meta WHERE key = 'geodb_last_updated'")
    row = cursor.fetchone()
    return row[0] if row else None


def store_geodb_to_r2(r2_client, rows):
    """Serialize parsed rows as gzip JSON and store to R2.

    Args:
        r2_client: R2Client instance
        rows: list of (ip_start, ip_end, cidr, country_code, region_code, city, ip_version)
    """
    from .r2_config import get_r2_prefix

    # Serialize as list of dicts for JSON
    data = [{
        's': r[0], 'e': r[1], 'c': r[2],
        'cc': r[3], 'rc': r[4], 'ci': r[5], 'v': r[6],
    } for r in rows]

    json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
    compressed = gzip.compress(json_bytes)

    prefix = get_r2_prefix()
    key = R2_GEODB_KEY_SUFFIX
    if prefix:
        key = f"{prefix.rstrip('/')}/{key}"

    r2_client._client.put_object(
        Bucket=r2_client._bucket,
        Key=key,
        Body=compressed,
        ContentType='application/json',
        ContentEncoding='gzip',
    )
    logger.info(f"Stored geodb to R2 ({len(compressed)} bytes, {len(rows)} entries)")


def load_geodb_from_r2(r2_client):
    """Load geodb from R2.

    Returns:
        list of (ip_start, ip_end, cidr, country_code, region_code, city, ip_version) or None
    """
    from .r2_config import get_r2_prefix

    prefix = get_r2_prefix()
    key = R2_GEODB_KEY_SUFFIX
    if prefix:
        key = f"{prefix.rstrip('/')}/{key}"

    try:
        response = r2_client._client.get_object(
            Bucket=r2_client._bucket,
            Key=key,
        )
        body = response['Body'].read()
        try:
            json_bytes = gzip.decompress(body)
        except OSError:
            json_bytes = body

        data = json.loads(json_bytes.decode('utf-8'))
        rows = [(d['s'], d['e'], d['c'], d['cc'], d['rc'], d['ci'], d['v']) for d in data]
        logger.info(f"Loaded {len(rows)} geodb entries from R2")
        return rows
    except Exception as e:
        if hasattr(e, 'response'):
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('NoSuchKey', '404', 'NotFound'):
                logger.debug("Geodb not found in R2")
                return None
        logger.warning(f"Error loading geodb from R2: {e}")
        return None


def hash_ip(ip_address: str) -> str:
    """Hash an IP address with salt for privacy. Returns hex digest."""
    salt = get_visitor_hash_salt()
    return hashlib.sha256(f"{salt}:{ip_address}".encode('utf-8')).hexdigest()


def init_geolocation(app):
    """Initialize geolocation on app startup.

    Tries: SQLite -> R2 -> leaves empty (background thread will populate).
    """
    if not is_geolocation_enabled():
        logger.info("Geolocation disabled")
        return

    global _geo_index

    with app.app_context():
        from app.db import get_db
        db = get_db()

        # Try SQLite first
        rows = load_geodb_from_sqlite(db)
        if rows:
            index = GeoIndex()
            index.load_from_rows(rows)
            _geo_index = index
            logger.info(f"Geolocation initialized from SQLite ({index.size} entries)")
            return

        # Try R2
        try:
            from .r2_client import get_r2_client
            r2 = get_r2_client()
            if r2:
                rows = load_geodb_from_r2(r2)
                if rows:
                    # Mirror to SQLite
                    store_geodb_to_sqlite(db, rows)
                    index = GeoIndex()
                    index.load_from_rows(rows)
                    _geo_index = index
                    logger.info(f"Geolocation initialized from R2 ({index.size} entries)")
                    return
        except Exception as e:
            logger.warning(f"Failed to load geodb from R2: {e}")

    logger.info("Geolocation index empty, waiting for background refresh")
