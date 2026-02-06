"""Tests for IP geolocation service."""
import gzip
import json
import os
import sqlite3

import pytest

from app.services.geolocation import (
    GeoIndex,
    GeoResult,
    _parse_cidr,
    _ip_to_hex,
    hash_ip,
    store_geodb_to_sqlite,
    load_geodb_from_sqlite,
    store_geodb_to_r2,
    load_geodb_from_r2,
)


# --- CIDR Parsing ---

class TestParseCidr:
    def test_ipv4_slash24(self):
        start, end, version = _parse_cidr('192.168.1.0/24')
        assert version == 4
        assert start == 'c0a80100'  # 192.168.1.0
        assert end == 'c0a801ff'    # 192.168.1.255

    def test_ipv4_slash32(self):
        start, end, version = _parse_cidr('10.0.0.1/32')
        assert version == 4
        assert start == end  # Single host
        assert start == '0a000001'

    def test_ipv4_slash16(self):
        start, end, version = _parse_cidr('172.16.0.0/16')
        assert version == 4
        assert start == 'ac100000'
        assert end == 'ac10ffff'

    def test_ipv6_slash48(self):
        start, end, version = _parse_cidr('2001:db8:abcd::/48')
        assert version == 6
        assert len(start) == 32
        assert len(end) == 32
        assert start == '20010db8abcd0000' + '0' * 16
        assert end == '20010db8abcd' + 'f' * 20

    def test_ipv6_slash128(self):
        start, end, version = _parse_cidr('::1/128')
        assert version == 6
        assert start == end
        assert start == '0' * 31 + '1'

    def test_invalid_cidr_raises(self):
        with pytest.raises(ValueError):
            _parse_cidr('not-a-cidr')


# --- IP to Hex ---

class TestIpToHex:
    def test_ipv4(self):
        hex_str, version = _ip_to_hex('192.168.1.100')
        assert version == 4
        assert hex_str == 'c0a80164'

    def test_ipv6(self):
        hex_str, version = _ip_to_hex('::1')
        assert version == 6
        assert hex_str == '0' * 31 + '1'


# --- GeoIndex ---

class TestGeoIndex:
    @pytest.fixture
    def sample_rows(self):
        """Sample rows: (ip_start, ip_end, cidr, country_code, region_code, city, ip_version)"""
        rows = []
        for cidr, cc, region, city in [
            ('192.168.1.0/24', 'US', 'CA', 'San Francisco'),
            ('10.0.0.0/8', 'CA', 'ON', 'Toronto'),
            ('172.16.0.0/16', 'GB', 'ENG', 'London'),
            ('2001:db8::/32', 'DE', 'BE', 'Berlin'),
        ]:
            s, e, v = _parse_cidr(cidr)
            rows.append((s, e, cidr, cc, region, city, v))
        return rows

    def test_lookup_found(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        result = idx.lookup('192.168.1.50')
        assert result is not None
        assert result.country_code == 'US'
        assert result.region_code == 'CA'
        assert result.city == 'San Francisco'

    def test_lookup_range_start(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        result = idx.lookup('10.0.0.0')
        assert result is not None
        assert result.country_code == 'CA'

    def test_lookup_range_end(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        result = idx.lookup('10.255.255.255')
        assert result is not None
        assert result.country_code == 'CA'

    def test_lookup_not_found(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        # 8.8.8.8 is not in any of our test ranges
        result = idx.lookup('8.8.8.8')
        assert result is None

    def test_lookup_ipv6(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        result = idx.lookup('2001:db8::1')
        assert result is not None
        assert result.country_code == 'DE'

    def test_lookup_invalid_ip(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        result = idx.lookup('not-an-ip')
        assert result is None

    def test_empty_index(self):
        idx = GeoIndex()
        idx.load_from_rows([])
        assert idx.size == 0
        assert idx.lookup('192.168.1.1') is None

    def test_size(self, sample_rows):
        idx = GeoIndex()
        idx.load_from_rows(sample_rows)
        # 3 IPv4 + 1 IPv6
        assert idx.size == 4


# --- IP Hashing ---

class TestHashIp:
    def test_deterministic(self, monkeypatch):
        monkeypatch.setenv('VISITOR_HASH_SALT', 'test-salt')
        h1 = hash_ip('192.168.1.1')
        h2 = hash_ip('192.168.1.1')
        assert h1 == h2

    def test_different_ips_differ(self, monkeypatch):
        monkeypatch.setenv('VISITOR_HASH_SALT', 'test-salt')
        h1 = hash_ip('192.168.1.1')
        h2 = hash_ip('192.168.1.2')
        assert h1 != h2

    def test_hex_format(self, monkeypatch):
        monkeypatch.setenv('VISITOR_HASH_SALT', 'test-salt')
        h = hash_ip('10.0.0.1')
        assert len(h) == 64  # SHA-256 hex digest
        assert all(c in '0123456789abcdef' for c in h)

    def test_different_salt_differs(self, monkeypatch):
        monkeypatch.setenv('VISITOR_HASH_SALT', 'salt-a')
        h1 = hash_ip('192.168.1.1')
        monkeypatch.setenv('VISITOR_HASH_SALT', 'salt-b')
        h2 = hash_ip('192.168.1.1')
        assert h1 != h2


# --- SQLite Store/Load ---

class TestSqliteStoreLoad:
    @pytest.fixture
    def geo_db(self, tmp_path):
        db_path = tmp_path / 'test.sqlite'
        conn = sqlite3.connect(str(db_path))
        from app.db import get_schema
        conn.executescript(get_schema())
        conn.commit()
        yield conn
        conn.close()

    def test_round_trip(self, geo_db):
        rows = [
            ('c0a80100', 'c0a801ff', '192.168.1.0/24', 'US', 'CA', 'LA', 4),
            ('0a000000', '0affffff', '10.0.0.0/8', 'CA', 'ON', 'Toronto', 4),
        ]
        store_geodb_to_sqlite(geo_db, rows)
        loaded = load_geodb_from_sqlite(geo_db)
        assert len(loaded) == 2
        assert loaded[0][3] in ('US', 'CA')  # country_code

    def test_replace_on_store(self, geo_db):
        rows1 = [('c0a80100', 'c0a801ff', '192.168.1.0/24', 'US', 'CA', 'LA', 4)]
        store_geodb_to_sqlite(geo_db, rows1)

        rows2 = [('0a000000', '0affffff', '10.0.0.0/8', 'CA', 'ON', 'Toronto', 4)]
        store_geodb_to_sqlite(geo_db, rows2)

        loaded = load_geodb_from_sqlite(geo_db)
        assert len(loaded) == 1
        assert loaded[0][3] == 'CA'


# --- R2 Store/Load ---

class TestR2StoreLoad:
    def test_round_trip(self, r2_client_fixture):
        rows = [
            ('c0a80100', 'c0a801ff', '192.168.1.0/24', 'US', 'CA', 'LA', 4),
            ('0a000000', '0affffff', '10.0.0.0/8', 'CA', 'ON', 'Toronto', 4),
        ]
        store_geodb_to_r2(r2_client_fixture, rows)
        loaded = load_geodb_from_r2(r2_client_fixture)
        assert loaded is not None
        assert len(loaded) == 2

    def test_load_missing_returns_none(self, r2_client_fixture):
        result = load_geodb_from_r2(r2_client_fixture)
        assert result is None
