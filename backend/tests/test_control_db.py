from __future__ import annotations

import os
from uuid import uuid4

import pytest

from healer.control_db import ControlDB, NotFound
from healer.keys import parse_prefix


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not configured")
def test_project_key_lifecycle_against_postgres():
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        os.environ["TEST_DATABASE_URL"],
        min_size=1,
        max_size=2,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    db = ControlDB(pool)
    owner = f"test-{uuid4()}"
    other = f"test-{uuid4()}"
    try:
        project = db.create_project(owner, "owner@example.com", "Owner", "agent", "Test agent")
        assert not db.has_active_key(owner)
        assert db.projects(owner)[0]["id"] == project["id"]
        assert db.projects(other) == []
        with pytest.raises(NotFound):
            db.keys(other, project["id"])
        issued = db.create_key(owner, project["id"], ["runs:read", "jobs:pull"])
        key = issued.pop("key")
        assert db.has_active_key(owner)
        assert parse_prefix(key) == issued["prefix"]
        assert "key" not in db.keys(owner, project["id"])[0]
        with pool.connection() as conn:
            row = conn.execute("SELECT * FROM api_keys WHERE id=%s", (issued["id"],)).fetchone()
            assert key not in repr(row)
            assert row["key_hash"] != key
        assert db.authenticate(key)["project_id"] == project["id"]
        assert db.authenticate(key, "runs:write") is None
        assert db.authenticate_with_code(key, "runs:write")[1] == "missing_scope"
        with pool.connection() as conn:
            conn.execute(
                "UPDATE api_keys SET expires_at=now()-interval '1 second' WHERE id=%s",
                (issued["id"],),
            )
        assert db.authenticate_with_code(key)[1] == "expired_key"
        assert not db.has_active_key(owner)
        with pytest.raises(NotFound):
            db.revoke_key(other, project["id"], issued["id"])
        db.revoke_key(owner, project["id"], issued["id"])
        assert db.authenticate(key) is None
        assert db.authenticate_with_code(key)[1] == "revoked_key"
        assert not db.has_active_key(owner)
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM users WHERE google_sub=%s", (owner,))
        pool.close()
