"""Tests for visitor logging service."""
import sqlite3
import os

import pytest

from app.db import get_schema
from app.services.visitor_logging import (
    log_visitor,
    backup_visitors_to_r2,
    restore_visitors_from_r2,
)
from app.services.geolocation import GeoIndex, _parse_cidr, set_geo_index


@pytest.fixture
def visitor_db(tmp_path):
    db_path = tmp_path / 'test.sqlite'
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(get_schema())
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def enable_logging(monkeypatch):
    monkeypatch.setenv('ENABLE_VISITOR_LOGGING', '1')
    monkeypatch.setenv('ENABLE_GEOLOCATION', '1')
    monkeypatch.setenv('VISITOR_HASH_SALT', 'test-salt')


class TestLogVisitor:
    def test_first_visit_creates_row(self, visitor_db):
        result = log_visitor(visitor_db, '192.168.1.1', 'TestBrowser/1.0')
        assert result is not None
        assert result['ip_hash']
        row = visitor_db.execute('SELECT * FROM visitors').fetchone()
        assert row['visit_count'] == 1
        assert row['user_agent'] == 'TestBrowser/1.0'

    def test_subsequent_visits_increment_count(self, visitor_db):
        log_visitor(visitor_db, '192.168.1.1', 'Browser/1.0')
        log_visitor(visitor_db, '192.168.1.1', 'Browser/1.0')
        log_visitor(visitor_db, '192.168.1.1', 'Browser/1.0')

        row = visitor_db.execute('SELECT * FROM visitors').fetchone()
        assert row['visit_count'] == 3

    def test_disabled_returns_none(self, visitor_db, monkeypatch):
        monkeypatch.setenv('ENABLE_VISITOR_LOGGING', '0')
        result = log_visitor(visitor_db, '192.168.1.1', 'Browser/1.0')
        assert result is None
        count = visitor_db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
        assert count == 0

    def test_geo_data_populated_with_index(self, visitor_db):
        # Build a small geo index
        cidr = '192.168.1.0/24'
        s, e, v = _parse_cidr(cidr)
        rows = [(s, e, cidr, 'US', 'CA', 'San Francisco', v)]
        idx = GeoIndex()
        idx.load_from_rows(rows)
        set_geo_index(idx)

        try:
            result = log_visitor(visitor_db, '192.168.1.50', 'Browser/1.0')
            assert result['country_code'] == 'US'
            assert result['region_code'] == 'CA'
            assert result['city'] == 'San Francisco'

            row = visitor_db.execute('SELECT * FROM visitors').fetchone()
            assert row['country_code'] == 'US'
        finally:
            set_geo_index(None)

    def test_different_ips_create_different_rows(self, visitor_db):
        log_visitor(visitor_db, '192.168.1.1', 'Browser/1.0')
        log_visitor(visitor_db, '192.168.1.2', 'Browser/1.0')

        count = visitor_db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
        assert count == 2


class TestR2BackupRestore:
    def test_backup_restore_round_trip(self, visitor_db, r2_client_fixture):
        # Insert some visitors
        log_visitor(visitor_db, '10.0.0.1', 'Browser/1.0')
        log_visitor(visitor_db, '10.0.0.2', 'Browser/2.0')

        # Backup to R2
        backup_visitors_to_r2(visitor_db, r2_client_fixture)

        # Clear SQLite
        visitor_db.execute('DELETE FROM visitors')
        visitor_db.commit()
        assert visitor_db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0] == 0

        # Restore from R2
        restore_visitors_from_r2(visitor_db, r2_client_fixture)
        count = visitor_db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
        assert count == 2

    def test_restore_skips_if_data_exists(self, visitor_db, r2_client_fixture):
        log_visitor(visitor_db, '10.0.0.1', 'Browser/1.0')
        backup_visitors_to_r2(visitor_db, r2_client_fixture)

        # Add another visitor after backup
        log_visitor(visitor_db, '10.0.0.2', 'Browser/2.0')

        # Restore should skip since table has data
        restore_visitors_from_r2(visitor_db, r2_client_fixture)
        count = visitor_db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
        assert count == 2  # Still 2, not overwritten
