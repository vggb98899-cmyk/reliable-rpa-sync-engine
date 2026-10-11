from __future__ import annotations

from dataclasses import dataclass

from .domain import ActionKind, ExecutionPlan, Snapshot, TargetIdentity


class GateRejected(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GatePolicy:
    allowed_environment: str = "DEMO"
    max_writes: int = 100


def validate_source_rows(rows: tuple[dict, ...] | tuple) -> None:
    keys = [str(row.get("id") or "") for row in rows]
    if any(not key for key in keys):
        raise GateRejected("PRIMARY_KEY_EMPTY", "every row requires an id")
    if len(keys) != len(set(keys)):
        raise GateRejected("PRIMARY_KEY_DUPLICATE", "duplicate ids are not allowed")


def validate_plan(
    plan: ExecutionPlan,
    *,
    current_snapshot: Snapshot,
    current_target: TargetIdentity,
    policy: GatePolicy,
) -> None:
    if plan.snapshot_fingerprint != current_snapshot.fingerprint:
        raise GateRejected("SNAPSHOT_STALE", "snapshot fingerprint changed")
    if plan.target != current_target:
        raise GateRejected("TARGET_MISMATCH", "target identity changed")
    if current_target.environment != policy.allowed_environment:
        raise GateRejected("TARGET_ENVIRONMENT_REJECTED", "target environment is not allowed")
    if any(change.kind == ActionKind.CONFLICT for change in plan.changes):
        raise GateRejected("CONFLICT_PRESENT", "conflicts must be resolved before execution")
    writes = sum(change.kind in {ActionKind.CREATE, ActionKind.UPDATE} for change in plan.changes)
    if writes > policy.max_writes:
        raise GateRejected("BLAST_RADIUS_EXCEEDED", "planned writes exceed the configured limit")
