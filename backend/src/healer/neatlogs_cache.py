"""Per-user, per-project workflow trace cache for incremental NeatLogs reads."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Trace
from .neatlogs_client import NeatlogsClient
from .privacy import Redactor


class NeatlogsTraceCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""CREATE TABLE IF NOT EXISTS traces (
            user_id TEXT NOT NULL, project_id TEXT NOT NULL, workflow_name TEXT NOT NULL,
            trace_id TEXT NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY(user_id, project_id, workflow_name, trace_id)
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS sync_state (
            user_id TEXT NOT NULL, project_id TEXT NOT NULL, workflow_name TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            PRIMARY KEY(user_id, project_id, workflow_name)
        )""")
        return connection

    def sync(
        self, user_id: str, project_id: str, workflow_name: str, client: NeatlogsClient
    ) -> list[Trace]:
        if not user_id or not project_id or not workflow_name:
            raise ValueError("User, project, and workflow are required")
        with closing(self._connect()) as database:
            row = database.execute(
                """SELECT synced_at FROM sync_state
                WHERE user_id=? AND project_id=? AND workflow_name=?""",
                (user_id, project_id, workflow_name),
            ).fetchone()
        from_timestamp = None
        if row:
            previous = datetime.fromisoformat(row[0])
            from_timestamp = (previous - timedelta(minutes=5)).isoformat()
        started = datetime.now(UTC).isoformat()
        incoming = client.list_traces(
            since="all",
            limit=None,
            max_pages=None,
            from_timestamp=from_timestamp,
            workflow_name=workflow_name,
        )
        redactor = Redactor()
        with closing(self._connect()) as database, database:
            for trace in incoming:
                safe = redactor.redact(trace.to_dict())
                safe["id"] = trace.id
                for stored, original in zip(safe["spans"], trace.spans, strict=True):
                    stored["id"] = original.id
                    stored["trace_id"] = original.trace_id
                    stored["parent_id"] = original.parent_id
                database.execute(
                    """INSERT INTO traces(user_id,project_id,workflow_name,trace_id,body)
                    VALUES(?,?,?,?,?) ON CONFLICT(user_id,project_id,workflow_name,trace_id)
                    DO UPDATE SET body=excluded.body""",
                    (
                        user_id,
                        project_id,
                        workflow_name,
                        trace.id,
                        json.dumps(safe, ensure_ascii=False),
                    ),
                )
            database.execute(
                """INSERT INTO sync_state(user_id,project_id,workflow_name,synced_at)
                VALUES(?,?,?,?) ON CONFLICT(user_id,project_id,workflow_name)
                DO UPDATE SET synced_at=excluded.synced_at""",
                (user_id, project_id, workflow_name, started),
            )
        return self.list(user_id, project_id, workflow_name)

    def list(self, user_id: str, project_id: str, workflow_name: str) -> list[Trace]:
        with closing(self._connect()) as database:
            rows = database.execute(
                """SELECT body FROM traces
                WHERE user_id=? AND project_id=? AND workflow_name=?""",
                (user_id, project_id, workflow_name),
            ).fetchall()
        return [Trace.from_dict(json.loads(row[0]), source="neatlogs") for row in rows]
