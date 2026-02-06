"""Visitor logging with IP geolocation.

Records unique visitors (deduped by hashed IP) with optional geo data.
Backs up visitor logs to R2 periodically; restores from R2 on startup if empty.
"""
import gzip
import json
import logging
from typing import Optional

from .config import is_visitor_logging_enabled, is_geolocation_enabled
from .geolocation import hash_ip, get_geo_index

logger = logging.getLogger('visitor_logging')


def log_visitor(db, ip_address: str, user_agent: str = '') -> Optional[dict]:
    """Record a visitor, upserting by hashed IP.

    Returns dict with ip_hash and geo info, or None if logging disabled.
    """
    if not is_visitor_logging_enabled():
        return None

    ip_hash = hash_ip(ip_address)

    # Geo lookup
    country_code = None
    region_code = None
    city = None

    if is_geolocation_enabled():
        geo_index = get_geo_index()
        if geo_index:
            result = geo_index.lookup(ip_address)
            if result:
                country_code = result.country_code
                region_code = result.region_code
                city = result.city

    # Truncate user agent to prevent storage bloat
    if user_agent and len(user_agent) > 512:
        user_agent = user_agent[:512]

    db.execute('''
        INSERT INTO visitors (ip_hash, country_code, region_code, city, user_agent)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ip_hash) DO UPDATE SET
            country_code = COALESCE(excluded.country_code, visitors.country_code),
            region_code = COALESCE(excluded.region_code, visitors.region_code),
            city = COALESCE(excluded.city, visitors.city),
            user_agent = excluded.user_agent,
            last_seen = datetime('now'),
            visit_count = visitors.visit_count + 1
    ''', (ip_hash, country_code, region_code, city, user_agent))
    db.commit()

    return {
        'ip_hash': ip_hash,
        'country_code': country_code,
        'region_code': region_code,
        'city': city,
    }


def backup_visitors_to_r2(db, r2_client):
    """Export all visitor rows as gzip JSON to R2."""
    from .r2_config import get_r2_prefix

    rows = db.execute(
        'SELECT ip_hash, country_code, region_code, city, user_agent, '
        'first_seen, last_seen, visit_count FROM visitors'
    ).fetchall()

    if not rows:
        logger.info("No visitors to back up")
        return

    data = [{
        'h': r[0], 'cc': r[1], 'rc': r[2], 'ci': r[3],
        'ua': r[4], 'fs': r[5], 'ls': r[6], 'vc': r[7],
    } for r in rows]

    json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
    compressed = gzip.compress(json_bytes)

    prefix = get_r2_prefix()
    key = 'visitors/snapshot.json.gz'
    if prefix:
        key = f"{prefix.rstrip('/')}/{key}"

    r2_client._client.put_object(
        Bucket=r2_client._bucket,
        Key=key,
        Body=compressed,
        ContentType='application/json',
        ContentEncoding='gzip',
    )
    logger.info(f"Backed up {len(rows)} visitors to R2 ({len(compressed)} bytes)")


def restore_visitors_from_r2(db, r2_client):
    """Restore visitors from R2 if SQLite visitors table is empty."""
    from .r2_config import get_r2_prefix

    # Check if table already has data
    count = db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
    if count > 0:
        logger.debug(f"Visitors table has {count} rows, skipping R2 restore")
        return

    prefix = get_r2_prefix()
    key = 'visitors/snapshot.json.gz'
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

        for d in data:
            db.execute('''
                INSERT OR IGNORE INTO visitors
                    (ip_hash, country_code, region_code, city, user_agent, first_seen, last_seen, visit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (d['h'], d.get('cc'), d.get('rc'), d.get('ci'),
                  d.get('ua'), d['fs'], d['ls'], d['vc']))
        db.commit()
        logger.info(f"Restored {len(data)} visitors from R2")

    except Exception as e:
        if hasattr(e, 'response'):
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('NoSuchKey', '404', 'NotFound'):
                logger.debug("No visitor backup found in R2")
                return
        logger.warning(f"Error restoring visitors from R2: {e}")
