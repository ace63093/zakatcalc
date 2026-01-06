"""R2 configuration from environment variables.

NEVER log credentials. All access via getters only.
"""
import os


def get_r2_endpoint() -> str | None:
    """R2 endpoint URL."""
    return os.environ.get('R2_ENDPOINT_URL')


def get_r2_bucket() -> str | None:
    """R2 bucket name."""
    return os.environ.get('R2_BUCKET')


def get_r2_access_key() -> str | None:
    """R2 access key ID. NEVER LOG THIS."""
    return os.environ.get('R2_ACCESS_KEY_ID')


def get_r2_secret_key() -> str | None:
    """R2 secret access key. NEVER LOG THIS."""
    return os.environ.get('R2_SECRET_ACCESS_KEY')


def get_r2_prefix() -> str:
    """Optional prefix for all R2 keys (e.g., 'zakat-app/pricing/')."""
    return os.environ.get('R2_PREFIX', '')


def is_r2_enabled() -> bool:
    """Check if R2 is fully configured."""
    return os.environ.get('R2_ENABLED', '').lower() in ('1', 'true', 'yes') and all([
        get_r2_endpoint(),
        get_r2_bucket(),
        get_r2_access_key(),
        get_r2_secret_key(),
    ])
