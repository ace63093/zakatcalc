"""Visitor logging with IP geolocation.

Records unique visitors (deduped by IP string) with optional geo data.
Backs up visitor logs to R2 periodically; restores from R2 on startup if empty.
"""
import gzip
import json
import logging
from typing import Optional

from .config import is_visitor_logging_enabled, is_geolocation_enabled
from .geolocation import hash_ip, get_geo_index

logger = logging.getLogger('visitor_logging')


def _normalize_host(host: str) -> str:
    """Normalize host header to lowercase hostname without port."""
    if not host:
        return ''

    value = host.strip().lower()
    if not value:
        return ''

    # IPv6 literal in brackets can include port after "]:".
    if value.startswith('['):
        end = value.find(']')
        if end != -1:
            return value[:end + 1]

    if ':' in value:
        return value.split(':', 1)[0]
    return value


def log_visitor(db, ip_address: str, user_agent: str = '', host: str = '') -> Optional[dict]:
    """Record a visitor, upserting by IP string.

    Returns dict with ip_hash (legacy key storing plain IP) and geo info, or None.
    """
    if not is_visitor_logging_enabled():
        return None

    ip_identity = (ip_address or '').strip()
    if not ip_identity:
        return None

    # Best-effort migration for legacy hashed rows: if a row still uses the old hash
    # for this IP and no plain-IP row exists yet, rewrite the key to plain IP.
    legacy_hash = hash_ip(ip_identity)
    if legacy_hash != ip_identity:
        db.execute(
            '''
            UPDATE visitors
            SET ip_hash = ?
            WHERE ip_hash = ?
              AND NOT EXISTS (
                  SELECT 1 FROM visitors existing WHERE existing.ip_hash = ?
              )
            ''',
            (ip_identity, legacy_hash, ip_identity),
        )
        try:
            db.execute(
                '''
                UPDATE visitor_domains
                SET ip_hash = ?
                WHERE ip_hash = ?
                ''',
                (ip_identity, legacy_hash),
            )
        except Exception:
            # If mixed legacy/plain rows would violate UNIQUE(ip_hash, host),
            # keep legacy domain rows and continue logging.
            pass

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

    normalized_host = _normalize_host(host)

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
    ''', (ip_identity, country_code, region_code, city, user_agent))

    # Track per-domain activity for this visitor.
    if normalized_host:
        db.execute('''
            INSERT INTO visitor_domains (ip_hash, host)
            VALUES (?, ?)
            ON CONFLICT(ip_hash, host) DO UPDATE SET
                last_seen = datetime('now'),
                visit_count = visitor_domains.visit_count + 1
        ''', (ip_identity, normalized_host))
    db.commit()

    return {
        'ip_hash': ip_identity,
        'country_code': country_code,
        'region_code': region_code,
        'city': city,
        'host': normalized_host,
    }


def backup_visitors_to_r2(db, r2_client):
    """Export all visitor rows as gzip JSON to R2."""
    from .r2_config import get_r2_prefix

    rows = db.execute(
        'SELECT ip_hash, country_code, region_code, city, user_agent, '
        'first_seen, last_seen, visit_count FROM visitors'
    ).fetchall()
    domain_rows = db.execute(
        'SELECT ip_hash, host, first_seen, last_seen, visit_count FROM visitor_domains'
    ).fetchall()

    if not rows and not domain_rows:
        logger.info("No visitors to back up")
        return

    visitors_data = [{
        'h': r[0], 'ip': r[0], 'cc': r[1], 'rc': r[2], 'ci': r[3],
        'ua': r[4], 'fs': r[5], 'ls': r[6], 'vc': r[7],
    } for r in rows]
    domains_data = [{
        'h': r[0], 'ip': r[0], 'd': r[1], 'fs': r[2], 'ls': r[3], 'vc': r[4],
    } for r in domain_rows]

    data = {
        'version': '2.0',
        'visitors': visitors_data,
        'domains': domains_data,
    }

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
    logger.info(
        f"Backed up {len(rows)} visitors and {len(domain_rows)} domain rows "
        f"to R2 ({len(compressed)} bytes)"
    )


def restore_visitors_from_r2(db, r2_client):
    """Restore visitors from R2 if SQLite visitors table is empty."""
    from .r2_config import get_r2_prefix

    # Skip restore only when both tables already have data.
    visitor_count = db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
    domain_count = db.execute('SELECT COUNT(*) FROM visitor_domains').fetchone()[0]
    if visitor_count > 0 and domain_count > 0:
        logger.debug(
            f"Visitors tables already populated (visitors={visitor_count}, domains={domain_count}), "
            "skipping R2 restore"
        )
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

        payload = json.loads(json_bytes.decode('utf-8'))

        # Backward compatibility:
        # - v1 snapshot: list of visitor rows
        # - v2 snapshot: {"version":"2.0","visitors":[...],"domains":[...]}
        if isinstance(payload, list):
            visitors_data = payload
            domains_data = []
        else:
            visitors_data = payload.get('visitors', [])
            domains_data = payload.get('domains', [])

        for d in visitors_data:
            ip_value = d.get('ip') or d.get('h')
            if not ip_value:
                continue
            db.execute('''
                INSERT OR IGNORE INTO visitors
                    (ip_hash, country_code, region_code, city, user_agent, first_seen, last_seen, visit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ip_value, d.get('cc'), d.get('rc'), d.get('ci'),
                  d.get('ua'), d['fs'], d['ls'], d['vc']))

        for d in domains_data:
            ip_value = d.get('ip') or d.get('h')
            if not ip_value:
                continue
            db.execute('''
                INSERT OR IGNORE INTO visitor_domains
                    (ip_hash, host, first_seen, last_seen, visit_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (ip_value, d['d'], d['fs'], d['ls'], d['vc']))
        db.commit()
        logger.info(
            f"Restored {len(visitors_data)} visitors and {len(domains_data)} domain rows from R2"
        )

    except Exception as e:
        if hasattr(e, 'response'):
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('NoSuchKey', '404', 'NotFound'):
                logger.debug("No visitor backup found in R2")
                return
        logger.warning(f"Error restoring visitors from R2: {e}")
