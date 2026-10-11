from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import sqlite3

from .domain import OperationStatus


@dataclass(frozen=True)
class OperationRecord:
    operation_key: str
    status: OperationStatus
    external_id: str | None
    submit_count: int


class OperationLedger:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_ledger (
                operation_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                external_id TEXT,
                submit_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )

    def get(self, operation_key: str) -> OperationRecord | None:
        row = self.connection.execute(
            "SELECT operation_key, status, external_id, submit_count FROM operation_ledger WHERE operation_key = ?",
            (operation_key,),
        ).fetchone()
        return OperationRecord(row[0], OperationStatus(row[1]), row[2], row[3]) if row else None

    def reserve(self, operation_key: str) -> OperationRecord:
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO operation_ledger(operation_key,status,updated_at) VALUES(?,?,?)",
                (operation_key, OperationStatus.RESERVED, now),
            )
        return self.get(operation_key)  # type: ignore[return-value]

    def confirm_submission(self, operation_key: str, external_id: str) -> OperationRecord:
        with self.connection:
            row = self.connection.execute(
                "SELECT submit_count, external_id FROM operation_ledger WHERE operation_key = ?",
                (operation_key,),
            ).fetchone()
            if row is None:
                raise KeyError(operation_key)
            if row[1] and row[1] != external_id:
                raise RuntimeError("operation already bound to another external id")
            self.connection.execute(
                "UPDATE operation_ledger SET status=?,external_id=?,submit_count=?,updated_at=? WHERE operation_key=?",
                (
                    OperationStatus.CONFIRMED,
                    external_id,
                    max(1, row[0]),
                    datetime.now(UTC).isoformat(),
                    operation_key,
                ),
            )
        return self.get(operation_key)  # type: ignore[return-value]

    def mark_submit_started(self, operation_key: str) -> None:
        with self.connection:
            changed = self.connection.execute(
                "UPDATE operation_ledger SET submit_count=submit_count+1,updated_at=? WHERE operation_key=? AND submit_count=0",
                (datetime.now(UTC).isoformat(), operation_key),
            ).rowcount
        if changed != 1:
            raise RuntimeError("external submit already attempted")

    def mark_unknown(self, operation_key: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE operation_ledger SET status=?,updated_at=? WHERE operation_key=?",
                (OperationStatus.UNKNOWN, datetime.now(UTC).isoformat(), operation_key),
            )

    def mark_reconciled(self, operation_key: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE operation_ledger SET status=?,updated_at=? WHERE operation_key=?",
                (OperationStatus.RECONCILED, datetime.now(UTC).isoformat(), operation_key),
            )
