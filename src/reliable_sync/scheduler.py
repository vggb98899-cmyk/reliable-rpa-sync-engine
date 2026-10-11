from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sqlite3
from uuid import uuid4


class LeaseStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS leases(name TEXT PRIMARY KEY, token TEXT, expires_at TEXT)"
        )

    def claim(self, name: str, ttl_seconds: int = 60) -> str | None:
        now = datetime.now(UTC)
        token = uuid4().hex
        with self.connection:
            current = self.connection.execute(
                "SELECT token,expires_at FROM leases WHERE name=?", (name,)
            ).fetchone()
            if current and current[1] and datetime.fromisoformat(current[1]) > now:
                return None
            self.connection.execute(
                "INSERT OR REPLACE INTO leases(name,token,expires_at) VALUES(?,?,?)",
                (name, token, (now + timedelta(seconds=ttl_seconds)).isoformat()),
            )
        return token

    def release(self, name: str, token: str) -> bool:
        with self.connection:
            return self.connection.execute(
                "DELETE FROM leases WHERE name=? AND token=?", (name, token)
            ).rowcount == 1
