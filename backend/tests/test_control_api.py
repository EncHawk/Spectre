"""Real Postgres and HTTP-handler proof for the key creation path."""

from __future__ import annotations

import json
import os
import socket
import threading
from uuid import uuid4

import pytest

from healer.control_db import ControlDB
from healer.server import make_handler


def exchange(
    service,
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
    user: str | None = None,
) -> tuple[int, dict]:
    server_socket, client_socket = socket.socketpair()

    def handle() -> None:
        try:
            make_handler(service)(server_socket, ("local", 0), object())
        finally:
            server_socket.close()

    thread = threading.Thread(target=handle, daemon=True)
    thread.start()
    headers = [f"{method} {path} HTTP/1.0", "Host: localhost"]
    if token:
        headers.append(f"Authorization: Bearer {token}")
    if user:
        headers.extend(
            (
                f"X-Spectre-User-Id: {user}",
                "X-Spectre-User-Email: owner@example.com",
                "X-Spectre-User-Name: Owner",
            )
        )
    payload = json.dumps(body).encode() if body is not None else b""
    if body is not None:
        headers.extend(("Content-Type: application/json", f"Content-Length: {len(payload)}"))
    client_socket.settimeout(3)
    try:
        client_socket.sendall("\r\n".join(headers).encode() + b"\r\n\r\n" + payload)
        client_socket.shutdown(socket.SHUT_WR)
        response = b""
        while chunk := client_socket.recv(65536):
            response += chunk
    finally:
        client_socket.close()
        thread.join(timeout=3)
    header, data = response.split(b"\r\n\r\n", 1)
    return int(header.split(b" ", 2)[1]), json.loads(data)


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not configured")
def test_internal_create_and_machine_whoami():
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        os.environ["TEST_DATABASE_URL"],
        min_size=1,
        max_size=2,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    owner = f"test-{uuid4()}"

    class Service:
        token = "service-secret"
        control_db = ControlDB(pool)

    service = Service()
    try:
        assert exchange(service, "POST", "/internal/projects", body={}, user=owner)[0] == 401
        status, project_response = exchange(
            service,
            "POST",
            "/internal/projects",
            "service-secret",
            {"app_id": "orders", "name": "Orders"},
            owner,
        )
        assert status == 201
        project_id = project_response["project"]["id"]
        assert exchange(service, "GET", "/internal/access", "service-secret", user=owner) == (
            200,
            {"has_active_key": False},
        )
        key_path = f"/internal/projects/{project_id}/keys"
        status, issued = exchange(
            service, "POST", key_path, "service-secret", {"scopes": ["runs:read"]}, owner
        )
        assert status == 201
        key = issued["api_key"]["key"]
        assert exchange(service, "GET", "/internal/access", "service-secret", user=owner) == (
            200,
            {"has_active_key": True},
        )
        assert exchange(service, "GET", key_path, "service-secret", user="other-user")[0] == 404
        listed = exchange(service, "GET", key_path, "service-secret", user=owner)[1]["keys"]
        assert len(listed) == 1 and "key" not in listed[0] and "key_hash" not in listed[0]
        status, identity = exchange(service, "GET", "/v1/whoami", key)
        assert status == 200 and identity["project_id"] == project_id
        key_id = issued["api_key"]["id"]
        assert (
            exchange(service, "DELETE", f"{key_path}/{key_id}", "service-secret", user=owner)[0]
            == 200
        )
        assert exchange(service, "GET", "/internal/access", "service-secret", user=owner) == (
            200,
            {"has_active_key": False},
        )
        status, problem = exchange(service, "GET", "/v1/whoami", key)
        assert status == 401 and problem["code"] == "revoked_key"
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM users WHERE google_sub=%s", (owner,))
        pool.close()
