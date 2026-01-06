"""Fake R2/S3 client for testing without network calls."""
import io
from typing import Any


class FakeClientError(Exception):
    """Fake ClientError for testing."""

    def __init__(self, error_code: str = 'NoSuchKey'):
        self.response = {'Error': {'Code': error_code}}
        super().__init__(error_code)


class FakeR2:
    """In-memory S3-compatible client for testing."""

    def __init__(self):
        self._objects: dict[str, dict[str, Any]] = {}

    def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str = None,
        ContentEncoding: str = None,
    ):
        """Store object in memory."""
        self._objects[f"{Bucket}/{Key}"] = {
            'Body': Body,
            'ContentType': ContentType,
            'ContentEncoding': ContentEncoding,
            'ContentLength': len(Body),
        }

    def get_object(self, Bucket: str, Key: str) -> dict:
        """Retrieve object from memory."""
        full_key = f"{Bucket}/{Key}"
        if full_key not in self._objects:
            raise FakeClientError('NoSuchKey')

        obj = self._objects[full_key]
        return {
            'Body': io.BytesIO(obj['Body']),
            'ContentType': obj.get('ContentType'),
            'ContentEncoding': obj.get('ContentEncoding'),
            'ContentLength': obj.get('ContentLength'),
        }

    def head_object(self, Bucket: str, Key: str) -> dict:
        """Check object exists."""
        full_key = f"{Bucket}/{Key}"
        if full_key not in self._objects:
            raise FakeClientError('404')

        obj = self._objects[full_key]
        return {'ContentLength': obj.get('ContentLength', 0)}

    def get_paginator(self, operation: str):
        """Return fake paginator for list_objects_v2."""
        return FakePaginator(self)


class FakePaginator:
    """Fake paginator for list_objects_v2."""

    def __init__(self, fake_r2: FakeR2):
        self._fake_r2 = fake_r2

    def paginate(self, Bucket: str, Prefix: str = ''):
        """Yield pages of matching objects."""
        contents = []
        for full_key in self._fake_r2._objects:
            if full_key.startswith(f"{Bucket}/{Prefix}"):
                key = full_key[len(f"{Bucket}/"):]
                contents.append({'Key': key})

        yield {'Contents': contents}
