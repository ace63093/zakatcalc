"""File-based caching with atomic writes."""
import os
import json
import tempfile
from datetime import datetime, timezone

DATA_DIR = os.environ.get('DATA_DIR', './data')
CACHE_FILE = 'pricing_cache.json'
DEFAULT_TTL = 3600


def get_cache_path() -> str:
    return os.path.join(DATA_DIR, CACHE_FILE)


def read_cache() -> dict | None:
    """Read cache, return None if missing/expired/invalid."""
    path = get_cache_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        if not is_cache_valid(data):
            return None
        return data
    except (json.JSONDecodeError, IOError):
        return None


def write_cache(data: dict) -> None:
    """Atomic write: temp file then rename."""
    path = get_cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, path)
    except:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def is_cache_valid(cache_data: dict, ttl: int = DEFAULT_TTL) -> bool:
    """Check if cache TTL has not expired."""
    if 'as_of' not in cache_data:
        return False
    try:
        as_of = datetime.fromisoformat(cache_data['as_of'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - as_of).total_seconds()
        return age < ttl
    except (ValueError, TypeError):
        return False


def clear_cache() -> None:
    path = get_cache_path()
    if os.path.exists(path):
        os.unlink(path)
