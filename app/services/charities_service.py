"""R2 storage for the charity directory."""
import gzip
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_R2_KEY_SUFFIX = "charities/directory.json.gz"
_cache: list | None = None  # In-memory cache; cleared by invalidate_cache()


def _r2_key() -> str:
    from app.services.r2_config import get_r2_prefix
    prefix = get_r2_prefix()
    return f"{prefix.rstrip('/')}/{_R2_KEY_SUFFIX}" if prefix else _R2_KEY_SUFFIX


def load_from_r2(r2_client) -> list | None:
    """Download and decompress charities from R2. Returns list or None."""
    try:
        key = _r2_key()
        resp = r2_client._client.get_object(Bucket=r2_client._bucket, Key=key)
        body = resp["Body"].read()
        try:
            body = gzip.decompress(body)
        except OSError:
            pass  # already decompressed by client
        payload = json.loads(body.decode("utf-8"))
        charities = payload.get("charities", [])
        if not charities:
            return None
        logger.info("Loaded %d charities from R2", len(charities))
        return charities
    except Exception as e:
        if hasattr(e, "response"):
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                logger.debug("Charities not found in R2")
                return None
        logger.warning("Failed to load charities from R2: %s", e)
        return None


def save_to_r2(r2_client, charities: list) -> bool:
    """Compress and upload charities to R2. Returns True on success."""
    try:
        key = _r2_key()
        payload = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "charities": charities,
        }
        compressed = gzip.compress(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        r2_client._client.put_object(
            Bucket=r2_client._bucket,
            Key=key,
            Body=compressed,
            ContentType="application/json",
            ContentEncoding="gzip",
        )
        logger.info("Saved %d charities to R2 (%d bytes)", len(charities), len(compressed))
        return True
    except Exception as e:
        logger.warning("Failed to save charities to R2: %s", e)
        return False


def get_charities(r2_client=None) -> list:
    """Return charities from in-memory cache → R2 → hardcoded fallback."""
    global _cache
    if _cache is not None:
        return _cache

    if r2_client:
        charities = load_from_r2(r2_client)
        if charities:
            _cache = charities
            return _cache

    from app.content.charities import CHARITIES
    return list(CHARITIES)


def invalidate_cache() -> None:
    """Clear the in-memory cache so the next call reloads from R2."""
    global _cache
    _cache = None
