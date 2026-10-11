from __future__ import annotations

import sqlite3
from uuid import uuid4

from .adapters import MockTarget, SourceAdapter, TargetAdapter, UnknownWriteResult
from .domain import ActionKind, ExecutionPlan, ExecutionResult, JobStatus, Snapshot, TargetIdentity
from .gates import GatePolicy, validate_plan, validate_source_rows
from .ledger import OperationLedger
from .planning import build_preview, freeze_plan
from .retry import retry_read


class SyncEngine:
    def __init__(
        self,
        source: SourceAdapter,
        target: TargetAdapter,
        *,
        connection: sqlite3.Connection | None = None,
        policy: GatePolicy | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self.ledger = OperationLedger(connection or sqlite3.connect(":memory:"))
        self.policy = policy or GatePolicy()

    def acquire_snapshot(self, operation_key: str) -> Snapshot:
        record = self.ledger.reserve(operation_key)
        if record.external_id is None:
            self.ledger.mark_submit_started(operation_key)
            export_id = self.source.export_once(operation_key)
            record = self.ledger.confirm_submission(operation_key, export_id)
        rows = retry_read(lambda: self.source.read_export(record.external_id or ""))
        frozen_rows = tuple(dict(row) for row in rows)
        validate_source_rows(frozen_rows)
        return Snapshot.build(f"snapshot-{uuid4().hex[:12]}", list(frozen_rows))

    def prepare(self, snapshot: Snapshot) -> ExecutionPlan:
        target = TargetIdentity(*self.target.identity())
        current = retry_read(self.target.read_records)
        preview = build_preview(snapshot, target, {k: dict(v) for k, v in current.items()})
        return freeze_plan(preview)

    def execute(self, plan: ExecutionPlan, snapshot: Snapshot, *, confirmed: bool) -> ExecutionResult:
        if not confirmed:
            raise PermissionError("manual confirmation is required")
        current_target = TargetIdentity(*self.target.identity())
        validate_plan(plan, current_snapshot=snapshot, current_target=current_target, policy=self.policy)
        creates = [dict(c.after or {}) for c in plan.changes if c.kind == ActionKind.CREATE]
        updates = [dict(c.after or {}) for c in plan.changes if c.kind == ActionKind.UPDATE]
        operation_key = f"write:{plan.fingerprint}"
        record = self.ledger.reserve(operation_key)
        if record.submit_count:
            raise RuntimeError("write execution already attempted")
        self.ledger.mark_submit_started(operation_key)
        try:
            if creates:
                self.target.create_records(creates)
            if updates:
                self.target.update_records(updates)
        except UnknownWriteResult:
            self.ledger.mark_unknown(operation_key)
            raise
        current = self.target.read_records()
        expected = creates + updates
        matched = sum(current.get(str(row["id"])) == row for row in expected)
        if matched != len(expected):
            self.ledger.mark_unknown(operation_key)
            return ExecutionResult(
                JobStatus.NEEDS_ATTENTION,
                created=len(creates),
                updated=len(updates),
                noop=sum(c.kind == ActionKind.NOOP for c in plan.changes),
                readback_expected=len(expected),
                readback_matched=matched,
                evidence={"failure": "READBACK_MISMATCH"},
            )
        self.ledger.mark_reconciled(operation_key)
        return ExecutionResult(
            JobStatus.SUCCESS,
            created=len(creates),
            updated=len(updates),
            noop=sum(c.kind == ActionKind.NOOP for c in plan.changes),
            readback_expected=len(expected),
            readback_matched=matched,
        )
