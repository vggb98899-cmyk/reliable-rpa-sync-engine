from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class SourceAdapter(Protocol):
    def export_once(self, operation_key: str) -> str: ...
    def read_export(self, export_id: str) -> list[Mapping[str, Any]]: ...


class TargetAdapter(Protocol):
    def identity(self) -> tuple[str, str, str]: ...
    def read_records(self) -> dict[str, Mapping[str, Any]]: ...
    def create_records(self, rows: list[Mapping[str, Any]]) -> None: ...
    def update_records(self, rows: list[Mapping[str, Any]]) -> None: ...


@dataclass
class MockSource:
    rows: list[Mapping[str, Any]]
    submit_count: int = 0
    transient_read_failures: int = 0

    def export_once(self, operation_key: str) -> str:
        self.submit_count += 1
        return f"mock-export-{operation_key}"

    def read_export(self, export_id: str) -> list[Mapping[str, Any]]:
        if self.transient_read_failures:
            self.transient_read_failures -= 1
            raise TimeoutError("simulated read-only timeout")
        return [dict(row) for row in self.rows]


class UnknownWriteResult(RuntimeError):
    """The remote write may have happened; retrying would be unsafe."""


@dataclass
class MockTarget:
    target_id: str
    environment: str
    schema_fingerprint: str
    records: dict[str, Mapping[str, Any]]
    create_calls: int = 0
    update_calls: int = 0
    fail_next_write_unknown: bool = False

    def identity(self) -> tuple[str, str, str]:
        return self.target_id, self.environment, self.schema_fingerprint

    def read_records(self) -> dict[str, Mapping[str, Any]]:
        return {key: dict(row) for key, row in self.records.items()}

    def create_records(self, rows: list[Mapping[str, Any]]) -> None:
        self.create_calls += 1
        for row in rows:
            self.records[str(row["id"])] = dict(row)
        if self.fail_next_write_unknown:
            self.fail_next_write_unknown = False
            raise UnknownWriteResult("simulated unknown create result")

    def update_records(self, rows: list[Mapping[str, Any]]) -> None:
        self.update_calls += 1
        for row in rows:
            self.records[str(row["id"])] = dict(row)
        if self.fail_next_write_unknown:
            self.fail_next_write_unknown = False
            raise UnknownWriteResult("simulated unknown update result")
