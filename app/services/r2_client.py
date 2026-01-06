"""Cloudflare R2 client for pricing snapshots.

Uses S3-compatible API via boto3. Stores gzip-compressed JSON.
NEVER logs credentials.
"""
import gzip
import json
import logging
from datetime import date
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .r2_config import (
    get_r2_endpoint,
    get_r2_bucket,
    get_r2_access_key,
    get_r2_secret_key,
    get_r2_prefix,
    is_r2_enabled,
)

logger = logging.getLogger(__name__)


class R2Client:
    """S3-compatible client for Cloudflare R2 pricing snapshots."""

    def __init__(self, s3_client=None):
        """Initialize R2 client.

        Args:
            s3_client: Optional boto3 S3 client (for testing with FakeR2)
        """
        self._bucket = get_r2_bucket()
        self._prefix = get_r2_prefix()

        if s3_client is not None:
            self._client = s3_client
        else:
            self._client = boto3.client(
                's3',
                endpoint_url=get_r2_endpoint(),
                aws_access_key_id=get_r2_access_key(),
                aws_secret_access_key=get_r2_secret_key(),
                region_name='auto',
            )

    def _make_key(self, data_type: str, cadence: str, effective_date: date) -> str:
        """Generate R2 object key.

        Format: {prefix}pricing/{type}/{cadence}/{date}.json.gz
        """
        date_str = effective_date.isoformat() if isinstance(effective_date, date) else effective_date
        key = f"pricing/{data_type}/{cadence}/{date_str}.json.gz"
        if self._prefix:
            key = f"{self._prefix.rstrip('/')}/{key}"
        return key

    def put_snapshot(
        self,
        data_type: str,
        cadence: str,
        effective_date: date,
        payload: dict[str, Any],
    ) -> str:
        """Store gzip-compressed JSON snapshot.

        Args:
            data_type: 'fx', 'metals', or 'crypto'
            cadence: 'daily', 'weekly', or 'monthly'
            effective_date: Snapshot effective date
            payload: Snapshot data (must include effective_date, cadence, base, data)

        Returns:
            R2 key on success

        Raises:
            ClientError on R2 failure
        """
        key = self._make_key(data_type, cadence, effective_date)

        # Ensure payload has required fields
        full_payload = {
            'version': '1.0',
            'type': data_type,
            'cadence': cadence,
            'effective_date': effective_date.isoformat() if isinstance(effective_date, date) else effective_date,
            'base': 'USD',
            **payload,
        }

        # Compress JSON
        json_bytes = json.dumps(full_payload, separators=(',', ':')).encode('utf-8')
        compressed = gzip.compress(json_bytes)

        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=compressed,
            ContentType='application/json',
            ContentEncoding='gzip',
        )

        logger.info(f"R2: Uploaded {data_type}/{cadence}/{effective_date} ({len(compressed)} bytes)")
        return key

    def get_snapshot(
        self,
        data_type: str,
        cadence: str,
        effective_date: date,
    ) -> dict[str, Any] | None:
        """Retrieve and decompress snapshot.

        Returns:
            Snapshot dict or None if not found
        """
        key = self._make_key(data_type, cadence, effective_date)

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            compressed = response['Body'].read()
            json_bytes = gzip.decompress(compressed)
            payload = json.loads(json_bytes.decode('utf-8'))
            logger.info(f"R2: Downloaded {data_type}/{cadence}/{effective_date}")
            return payload
        except Exception as e:
            # Handle both botocore.exceptions.ClientError and FakeClientError
            if hasattr(e, 'response'):
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ('NoSuchKey', '404', 'NotFound'):
                    logger.debug(f"R2: Not found {data_type}/{cadence}/{effective_date}")
                    return None
            logger.warning(f"R2: Error getting {key}: {e}")
            raise

    def has_snapshot(
        self,
        data_type: str,
        cadence: str,
        effective_date: date,
    ) -> bool:
        """Check if snapshot exists (HEAD request).

        Returns:
            True if exists, False otherwise
        """
        key = self._make_key(data_type, cadence, effective_date)

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception as e:
            # Handle both botocore.exceptions.ClientError and FakeClientError
            if hasattr(e, 'response'):
                return False
            raise

    def list_snapshots(
        self,
        data_type: str | None = None,
        cadence: str | None = None,
    ) -> list[str]:
        """List snapshot keys with optional filters.

        Returns:
            List of R2 keys matching the filter
        """
        prefix = self._prefix or ''
        if data_type:
            prefix = f"{prefix}pricing/{data_type}/"
            if cadence:
                prefix = f"{prefix}{cadence}/"
        else:
            prefix = f"{prefix}pricing/"

        keys = []
        paginator = self._client.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                keys.append(obj['Key'])

        return keys


def get_r2_client() -> R2Client | None:
    """Get R2 client if configured, else None."""
    if not is_r2_enabled():
        return None
    return R2Client()
