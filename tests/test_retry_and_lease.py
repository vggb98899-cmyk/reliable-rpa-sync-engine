import sqlite3

import pytest

from reliable_sync.retry import ReadRetryExhausted, retry_read
from reliable_sync.scheduler import LeaseStore


def test_read_retry_recovers_from_timeout():
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    assert retry_read(operation, backoff_seconds=(0, 0)) == "ok"
    assert calls == 3


def test_read_retry_stops_after_bound():
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        raise ConnectionError("offline")

    with pytest.raises(ReadRetryExhausted):
        retry_read(operation, attempts=3, backoff_seconds=(0, 0))
    assert calls == 3


def test_non_retryable_error_is_immediate():
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        raise PermissionError("forbidden")

    with pytest.raises(PermissionError):
        retry_read(operation)
    assert calls == 1


def test_lease_prevents_parallel_claim():
    store = LeaseStore(sqlite3.connect(":memory:"))
    token = store.claim("schedule")
    assert token
    assert store.claim("schedule") is None


def test_lease_release_requires_owner_token():
    store = LeaseStore(sqlite3.connect(":memory:"))
    token = store.claim("schedule")
    assert token
    assert not store.release("schedule", "wrong-token")
    assert store.release("schedule", token)
    assert store.claim("schedule")
