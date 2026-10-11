from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Mapping


class JobStatus(StrEnum):
    CREATED = "CREATED"
    PREVIEW_READY = "PREVIEW_READY"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class OperationStatus(StrEnum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"


class ActionKind(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    NOOP = "NOOP"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class TargetIdentity:
    target_id: str
    environment: str
    schema_fingerprint: str


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    rows: tuple[Mapping[str, Any], ...]
    fingerprint: str

    @classmethod
    def build(cls, snapshot_id: str, rows: list[Mapping[str, Any]]) -> "Snapshot":
        frozen = tuple(dict(row) for row in rows)
        payload = json.dumps(frozen, ensure_ascii=False, sort_keys=True, default=str)
        return cls(snapshot_id, frozen, sha256(payload.encode()).hexdigest())


@dataclass(frozen=True)
class Change:
    kind: ActionKind
    key: str
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Preview:
    preview_id: str
    snapshot_fingerprint: str
    target: TargetIdentity
    changes: tuple[Change, ...]

    def count(self, kind: ActionKind) -> int:
        return sum(change.kind == kind for change in self.changes)


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    preview_id: str
    snapshot_fingerprint: str
    target: TargetIdentity
    changes: tuple[Change, ...]
    fingerprint: str

    @classmethod
    def freeze(cls, plan_id: str, preview: Preview) -> "ExecutionPlan":
        payload = {
            "preview_id": preview.preview_id,
            "snapshot": preview.snapshot_fingerprint,
            "target": preview.target.__dict__,
            "changes": [
                {
                    "kind": c.kind,
                    "key": c.key,
                    "before": c.before,
                    "after": c.after,
                    "changed": c.changed_fields,
                }
                for c in preview.changes
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return cls(
            plan_id,
            preview.preview_id,
            preview.snapshot_fingerprint,
            preview.target,
            preview.changes,
            sha256(encoded.encode()).hexdigest(),
        )


@dataclass(frozen=True)
class ExecutionResult:
    status: JobStatus
    created: int = 0
    updated: int = 0
    noop: int = 0
    readback_expected: int = 0
    readback_matched: int = 0
    evidence: Mapping[str, Any] = field(default_factory=dict)
