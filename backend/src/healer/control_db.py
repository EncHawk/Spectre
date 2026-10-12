"""Postgres control-plane access shared by project and machine-key routes."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import UUID

from .keys import SCOPES, generate_key, parse_prefix, verify_key


class NotFound(Exception):
    pass


class InvalidInput(Exception):
    pass


class ControlDB:
    def __init__(self, pool: Any):
        self.pool = pool

    @classmethod
    def from_environment(cls) -> ControlDB | None:
        url = os.getenv("DATABASE_URL")
        if not url:
            return None
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        return cls(
            ConnectionPool(url, min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True)
        )

    def upsert_user(self, google_sub: str, email: str, name: str) -> str:
        if not google_sub or not email or not name:
            raise InvalidInput("User identity is required")
        with self.pool.connection() as conn:
            row = conn.execute(
                """INSERT INTO users (google_sub,email,name) VALUES (%s,%s,%s)
                ON CONFLICT (google_sub) DO UPDATE SET email=excluded.email,name=excluded.name
                RETURNING id""",
                (google_sub, email, name),
            ).fetchone()
            return str(row["id"])

    def projects(self, google_sub: str) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                """SELECT p.id,p.app_id,p.name,p.created_at FROM projects p
                JOIN users u ON u.id=p.user_id WHERE u.google_sub=%s ORDER BY p.created_at DESC""",
                (google_sub,),
            ).fetchall()
            return [_public(row) for row in rows]

    def has_active_key(self, google_sub: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(
                """SELECT EXISTS (
                    SELECT 1 FROM api_keys k
                    JOIN projects p ON p.id=k.project_id
                    JOIN users u ON u.id=p.user_id
                    WHERE u.google_sub=%s AND k.revoked_at IS NULL
                    AND (k.expires_at IS NULL OR k.expires_at > now())
                ) AS has_active_key""",
                (google_sub,),
            ).fetchone()
            return bool(row["has_active_key"])

    def create_project(
        self, google_sub: str, email: str, user_name: str, app_id: str, name: str
    ) -> dict[str, Any]:
        import re

        if not isinstance(app_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", app_id
        ):
            raise InvalidInput(
                "app_id must be 1–64 letters, numbers, dots, underscores, or hyphens"
            )
        if not isinstance(name, str) or not 1 <= len(name) <= 100:
            raise InvalidInput("Project name must be 1–100 characters")
        user_id = self.upsert_user(google_sub, email, user_name)
        with self.pool.connection() as conn:
            row = conn.execute(
                """INSERT INTO projects (user_id,app_id,name) VALUES (%s,%s,%s)
                ON CONFLICT (user_id,app_id) DO NOTHING RETURNING id,app_id,name,created_at""",
                (user_id, app_id, name),
            ).fetchone()
        if row is None:
            raise InvalidInput("A project with this app ID already exists")
        return _public(row)

    def _owned_project(self, conn: Any, google_sub: str, project_id: str) -> None:
        try:
            project_uuid = UUID(project_id)
        except ValueError as exc:
            raise NotFound("Project not found") from exc
        row = conn.execute(
            """SELECT 1 FROM projects p JOIN users u ON u.id=p.user_id
            WHERE p.id=%s AND u.google_sub=%s""",
            (project_uuid, google_sub),
        ).fetchone()
        if row is None:
            raise NotFound("Project not found")

    def keys(self, google_sub: str, project_id: str) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            self._owned_project(conn, google_sub, project_id)
            rows = conn.execute(
                """SELECT id,prefix,scopes,created_at,expires_at,last_used_at,revoked_at
                FROM api_keys WHERE project_id=%s ORDER BY created_at DESC""",
                (UUID(project_id),),
            ).fetchall()
            return [_public(row) for row in rows]

    def create_key(self, google_sub: str, project_id: str, scopes: list[str]) -> dict[str, Any]:
        if (
            not isinstance(scopes, list)
            or not scopes
            or any(not isinstance(scope, str) for scope in scopes)
            or len(scopes) != len(set(scopes))
            or not set(scopes) <= SCOPES
        ):
            raise InvalidInput("Choose one or more valid, distinct scopes")
        with self.pool.connection() as conn:
            self._owned_project(conn, google_sub, project_id)
            key, prefix, digest = generate_key()
            row = conn.execute(
                """INSERT INTO api_keys (project_id,prefix,key_hash,scopes)
                VALUES (%s,%s,%s,%s) RETURNING id,prefix,scopes,created_at,expires_at,last_used_at,revoked_at""",
                (UUID(project_id), prefix, digest, scopes),
            ).fetchone()
        return {**_public(row), "key": key}

    def revoke_key(self, google_sub: str, project_id: str, key_id: str) -> None:
        try:
            key_uuid = UUID(key_id)
        except ValueError as exc:
            raise NotFound("Key not found") from exc
        with self.pool.connection() as conn:
            self._owned_project(conn, google_sub, project_id)
            row = conn.execute(
                """UPDATE api_keys SET revoked_at=COALESCE(revoked_at,now())
                WHERE id=%s AND project_id=%s RETURNING id""",
                (key_uuid, UUID(project_id)),
            ).fetchone()
            if row is None:
                raise NotFound("Key not found")

    def authenticate(self, key: str, scope: str | None = None) -> dict[str, Any] | None:
        identity, _ = self.authenticate_with_code(key, scope)
        return identity

    def authenticate_with_code(
        self, key: str, scope: str | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        prefix = parse_prefix(key)
        if not prefix:
            return None, "invalid_key"
        with self.pool.connection() as conn:
            row = conn.execute(
                """SELECT k.key_hash,k.id,k.scopes,k.revoked_at,k.expires_at,
                p.id AS project_id,p.app_id FROM api_keys k JOIN projects p ON p.id=k.project_id
                WHERE k.prefix=%s""",
                (prefix,),
            ).fetchone()
            if row is None or not verify_key(key, row["key_hash"]):
                return None, "invalid_key"
            if row["revoked_at"] is not None:
                return None, "revoked_key"
            if row["expires_at"] and row["expires_at"] <= datetime.now(row["expires_at"].tzinfo):
                return None, "expired_key"
            if scope and scope not in row["scopes"]:
                return None, "missing_scope"
            conn.execute(
                """UPDATE api_keys SET last_used_at=now() WHERE id=%s
                AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')""",
                (row["id"],),
            )
            return (
                {
                    "project_id": str(row["project_id"]),
                    "app_id": row["app_id"],
                    "prefix": prefix,
                    "scopes": row["scopes"],
                },
                None,
            )


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat()
        if isinstance(value, datetime)
        else str(value)
        if isinstance(value, UUID)
        else value
        for key, value in row.items()
    }
