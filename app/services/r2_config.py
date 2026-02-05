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
    if os.environ.get('R2_ENABLED', '').lower() not in ('1', 'true', 'yes'):
        return False

    endpoint = get_r2_endpoint()
    bucket = get_r2_bucket()
    access_key = get_r2_access_key()
    secret_key = get_r2_secret_key()

    if not all([endpoint, bucket, access_key, secret_key]):
        return False

    placeholders = {
        'your-bucket-name',
        'your-access-key-id',
        'your-secret-access-key',
    }

    if bucket in placeholders or access_key in placeholders or secret_key in placeholders:
        return False

    if 'YOUR_ACCOUNT_ID' in endpoint:
        return False

    return True
