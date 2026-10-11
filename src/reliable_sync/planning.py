from __future__ import annotations

from uuid import uuid4

from .domain import ActionKind, Change, ExecutionPlan, Preview, Snapshot, TargetIdentity


def build_preview(
    snapshot: Snapshot,
    target: TargetIdentity,
    current: dict[str, dict],
) -> Preview:
    changes: list[Change] = []
    for row in snapshot.rows:
        key = str(row["id"])
        before = current.get(key)
        after = dict(row)
        if before is None:
            changes.append(Change(ActionKind.CREATE, key, None, after, tuple(after)))
            continue
        changed = tuple(sorted(field for field, value in after.items() if before.get(field) != value))
        changes.append(
            Change(ActionKind.UPDATE if changed else ActionKind.NOOP, key, before, after, changed)
        )
    return Preview(f"preview-{uuid4().hex[:12]}", snapshot.fingerprint, target, tuple(changes))


def freeze_plan(preview: Preview) -> ExecutionPlan:
    return ExecutionPlan.freeze(f"plan-{uuid4().hex[:12]}", preview)
