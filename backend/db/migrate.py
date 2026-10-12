"""Apply the control schema once, transactionally, without logging credentials."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import psycopg


def migrate() -> None:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    schema = Path(__file__).with_name("schema.sql").read_text()
    digest = hashlib.sha256(schema.encode()).hexdigest()
    with psycopg.connect(url, connect_timeout=15) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(173921846)")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now())""")
        conn.execute("ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY")
        existing = conn.execute(
            "SELECT checksum FROM schema_migrations WHERE version=%s", ("001",)
        ).fetchone()
        if existing:
            if existing[0] != digest:
                raise RuntimeError("Migration 001 checksum changed; add a new migration")
            print("Migration 001 already applied")
            return
        conn.execute(schema)
        conn.execute(
            "INSERT INTO schema_migrations(version,checksum) VALUES (%s,%s)", ("001", digest)
        )
    print("Migration 001 applied successfully")


if __name__ == "__main__":
    try:
        migrate()
    except (psycopg.Error, OSError, RuntimeError) as exc:
        # Driver errors can contain credentials or query parameters.
        print(f"Migration failed ({type(exc).__name__}); check database access and schema")
        raise SystemExit(1) from None
