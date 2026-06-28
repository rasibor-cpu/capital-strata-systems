"""
Tests for Shared Common Enterprise Foundation (backend/common)
"""

import os
import threading
import time
import pytest
from backend.common.exceptions import (
    CSSException,
    ValidationException,
    ConfigurationException,
    PersistenceException,
)
from backend.common.configuration import (
    NotificationConfig,
    ReportingConfig,
    OperationsConfig,
)
from backend.common.validation import validate_required_fields, validate_field_type
from backend.common.versioning import validate_schema_version
from backend.common.serialization import JSONSerializable
from backend.common.persistence import save_json, load_json, append_jsonl, load_jsonl


def test_exception_hierarchy():
    with pytest.raises(CSSException):
        raise ValidationException("invalid input")

    with pytest.raises(CSSException):
        raise PersistenceException("file failed")

    with pytest.raises(CSSException):
        raise ConfigurationException("bad config")


def test_validation_utilities():
    data = {"name": "CSS", "active": True}
    
    # Passes
    validate_required_fields(data, ["name", "active"])
    validate_field_type("name", "CSS", str)
    validate_field_type("active", True, bool)

    # Fails
    with pytest.raises(ValidationException):
        validate_required_fields(data, ["missing"])

    with pytest.raises(ValidationException):
        validate_field_type("name", 123, str)


def test_versioning_utility():
    # Passes
    validate_schema_version("1.0.0")
    validate_schema_version("1.2.3")

    # Fails (Incompatible major version)
    with pytest.raises(ValidationException):
        validate_schema_version("2.0.0")

    # Fails (Malformed strings)
    with pytest.raises(ValidationException):
        validate_schema_version("abc")


def test_configuration_validation():
    # Valid notification config
    config1 = NotificationConfig(max_retries=5, quiet_hours_start="22:00", quiet_hours_end="08:00")
    config1.validate()

    # Invalid retry count
    config2 = NotificationConfig(max_retries=-1)
    with pytest.raises(ConfigurationException):
        config2.validate()

    # Invalid quiet hours format
    config3 = NotificationConfig(quiet_hours_start="22:0")
    with pytest.raises(ConfigurationException):
        config3.validate()


class DummySerializable(JSONSerializable):
    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value

    def to_dict(self):
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["value"])


def test_serialization():
    obj = DummySerializable("Test", 42)
    
    json_str = obj.to_json()
    assert "Test" in json_str
    assert "42" in json_str

    cloned = DummySerializable.from_json(json_str)
    assert cloned.name == "Test"
    assert cloned.value == 42


def test_persistence_thread_safety(tmp_path):
    file_path = tmp_path / "thread_test.jsonl"
    lock = threading.Lock()

    def worker(idx):
        for i in range(10):
            append_jsonl(str(file_path), {"thread": idx, "index": i}, lock)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results = load_jsonl(str(file_path), lock)
    assert len(results) == 50
    thread_ids = [r["thread"] for r in results]
    for i in range(5):
        assert thread_ids.count(i) == 10
