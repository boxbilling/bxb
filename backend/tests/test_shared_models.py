"""Tests for shared model utilities."""

import uuid
from datetime import UTC, datetime

from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid, utc_now


class TestGenerateUuid:
    def test_returns_uuid(self):
        result = generate_uuid()
        assert isinstance(result, uuid.UUID)

    def test_returns_unique_values(self):
        results = {generate_uuid() for _ in range(10)}
        assert len(results) == 10

    def test_returns_uuid4(self):
        result = generate_uuid()
        assert result.version == 4


class TestUtcNow:
    def test_returns_datetime(self):
        result = utc_now()
        assert isinstance(result, datetime)

    def test_returns_utc(self):
        result = utc_now()
        assert result.tzinfo == UTC

    def test_returns_current_time(self):
        before = datetime.now(UTC)
        result = utc_now()
        after = datetime.now(UTC)
        assert before <= result <= after


class TestDefaultOrganizationId:
    def test_is_uuid(self):
        assert isinstance(DEFAULT_ORGANIZATION_ID, uuid.UUID)

    def test_value(self):
        assert str(DEFAULT_ORGANIZATION_ID) == "00000000-0000-0000-0000-000000000001"


class TestUUIDType:
    def test_cache_ok(self):
        assert UUIDType.cache_ok is True

    def test_process_bind_param_none(self):
        t = UUIDType()
        assert t.process_bind_param(None, None) is None

    def test_process_bind_param_uuid(self):
        t = UUIDType()
        val = uuid.uuid4()
        assert t.process_bind_param(val, None) == str(val)

    def test_process_bind_param_string(self):
        t = UUIDType()
        val = "12345678-1234-5678-1234-567812345678"
        assert t.process_bind_param(val, None) == val

    def test_process_result_value_none(self):
        t = UUIDType()
        assert t.process_result_value(None, None) is None

    def test_process_result_value_uuid(self):
        t = UUIDType()
        val = uuid.uuid4()
        assert t.process_result_value(val, None) is val

    def test_process_result_value_string(self):
        t = UUIDType()
        val = "12345678-1234-5678-1234-567812345678"
        result = t.process_result_value(val, None)
        assert isinstance(result, uuid.UUID)
        assert str(result) == val
