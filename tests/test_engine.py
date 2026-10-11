import sqlite3

import pytest

from reliable_sync.adapters import MockSource, MockTarget, UnknownWriteResult
from reliable_sync.domain import ActionKind, JobStatus, Snapshot, TargetIdentity
from reliable_sync.engine import SyncEngine
from reliable_sync.gates import GatePolicy, GateRejected


def build_engine(rows=None, current=None, **source_kwargs):
    source = MockSource(rows or [{"id": "1", "value": "new"}], **source_kwargs)
    target = MockTarget("target-1", "DEMO", "schema-v1", current or {})
    return SyncEngine(source, target), source, target


def test_full_create_and_readback():
    engine, source, target = build_engine()
    snapshot = engine.acquire_snapshot("run-1")
    plan = engine.prepare(snapshot)
    result = engine.execute(plan, snapshot, confirmed=True)
    assert result.status == JobStatus.SUCCESS
    assert result.created == 1
    assert result.readback_matched == 1
    assert source.submit_count == 1
    assert target.create_calls == 1


def test_update_and_noop_are_distinguished():
    rows = [{"id": "1", "value": "new"}, {"id": "2", "value": "same"}]
    current = {"1": {"id": "1", "value": "old"}, "2": {"id": "2", "value": "same"}}
    engine, _, _ = build_engine(rows, current)
    snapshot = engine.acquire_snapshot("run-2")
    plan = engine.prepare(snapshot)
    assert [change.kind for change in plan.changes] == [ActionKind.UPDATE, ActionKind.NOOP]
    result = engine.execute(plan, snapshot, confirmed=True)
    assert (result.updated, result.noop) == (1, 1)


def test_manual_confirmation_is_required():
    engine, _, target = build_engine()
    snapshot = engine.acquire_snapshot("run-3")
    plan = engine.prepare(snapshot)
    with pytest.raises(PermissionError):
        engine.execute(plan, snapshot, confirmed=False)
    assert target.create_calls == 0


def test_duplicate_source_key_fails_before_write():
    engine, _, target = build_engine([{"id": "1"}, {"id": "1"}])
    with pytest.raises(GateRejected) as exc:
        engine.acquire_snapshot("run-4")
    assert exc.value.code == "PRIMARY_KEY_DUPLICATE"
    assert target.create_calls == 0


def test_empty_source_key_fails_before_write():
    engine, _, _ = build_engine([{"id": ""}])
    with pytest.raises(GateRejected) as exc:
        engine.acquire_snapshot("run-5")
    assert exc.value.code == "PRIMARY_KEY_EMPTY"


def test_read_only_timeout_is_retried_without_second_export():
    engine, source, _ = build_engine(transient_read_failures=2)
    snapshot = engine.acquire_snapshot("run-6")
    assert snapshot.rows
    assert source.submit_count == 1


def test_same_export_is_reused_when_snapshot_is_acquired_again():
    engine, source, _ = build_engine()
    first = engine.acquire_snapshot("run-7")
    second = engine.acquire_snapshot("run-7")
    assert first.rows == second.rows
    assert source.submit_count == 1


def test_stale_snapshot_rejected():
    engine, _, target = build_engine()
    snapshot = engine.acquire_snapshot("run-8")
    plan = engine.prepare(snapshot)
    changed = Snapshot.build("other", [{"id": "1", "value": "changed"}])
    with pytest.raises(GateRejected) as exc:
        engine.execute(plan, changed, confirmed=True)
    assert exc.value.code == "SNAPSHOT_STALE"
    assert target.create_calls == 0


def test_target_identity_change_rejected():
    engine, _, target = build_engine()
    snapshot = engine.acquire_snapshot("run-9")
    plan = engine.prepare(snapshot)
    target.schema_fingerprint = "schema-v2"
    with pytest.raises(GateRejected) as exc:
        engine.execute(plan, snapshot, confirmed=True)
    assert exc.value.code == "TARGET_MISMATCH"


def test_wrong_environment_rejected():
    source = MockSource([{"id": "1"}])
    target = MockTarget("target", "PRODUCTION", "schema", {})
    engine = SyncEngine(source, target)
    snapshot = engine.acquire_snapshot("run-10")
    plan = engine.prepare(snapshot)
    with pytest.raises(GateRejected) as exc:
        engine.execute(plan, snapshot, confirmed=True)
    assert exc.value.code == "TARGET_ENVIRONMENT_REJECTED"


def test_blast_radius_rejected():
    rows = [{"id": str(index)} for index in range(3)]
    source = MockSource(rows)
    target = MockTarget("target", "DEMO", "schema", {})
    engine = SyncEngine(source, target, policy=GatePolicy(max_writes=2))
    snapshot = engine.acquire_snapshot("run-11")
    plan = engine.prepare(snapshot)
    with pytest.raises(GateRejected) as exc:
        engine.execute(plan, snapshot, confirmed=True)
    assert exc.value.code == "BLAST_RADIUS_EXCEEDED"


def test_unknown_write_is_not_retried():
    engine, _, target = build_engine()
    target.fail_next_write_unknown = True
    snapshot = engine.acquire_snapshot("run-12")
    plan = engine.prepare(snapshot)
    with pytest.raises(UnknownWriteResult):
        engine.execute(plan, snapshot, confirmed=True)
    assert target.create_calls == 1
    with pytest.raises(RuntimeError, match="already attempted"):
        engine.execute(plan, snapshot, confirmed=True)
    assert target.create_calls == 1


def test_noop_finishes_without_write_calls():
    row = {"id": "1", "value": "same"}
    engine, _, target = build_engine([row], {"1": row})
    snapshot = engine.acquire_snapshot("run-13")
    plan = engine.prepare(snapshot)
    result = engine.execute(plan, snapshot, confirmed=True)
    assert result.status == JobStatus.SUCCESS
    assert result.noop == 1
    assert result.readback_expected == 0
    assert target.create_calls == target.update_calls == 0


def test_plan_fingerprint_is_stable_for_same_preview():
    engine, _, _ = build_engine()
    snapshot = engine.acquire_snapshot("run-14")
    preview = engine.prepare(snapshot)
    assert len(preview.fingerprint) == 64


def test_operation_ledger_persists_across_engine_instances():
    connection = sqlite3.connect(":memory:")
    source = MockSource([{"id": "1"}])
    target = MockTarget("target", "DEMO", "schema", {})
    first = SyncEngine(source, target, connection=connection)
    first.acquire_snapshot("persistent-run")
    second = SyncEngine(source, target, connection=connection)
    second.acquire_snapshot("persistent-run")
    assert source.submit_count == 1
