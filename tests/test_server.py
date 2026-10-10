from __future__ import annotations

import json
import socket
import threading

import pytest

from healer.errors import ConfigurationError
from healer.server import ServerSettings, make_handler


class Service:
    token = "secret-token"

    def status(self):
        return {"status": "ready", "capabilities": {"local_fallback": True}}

    def scan(self, options):
        return {"count": 0, "findings": [], "options": options}


def exchange(request: bytes) -> tuple[int, dict]:
    server_socket, client_socket = socket.socketpair()

    def handle() -> None:
        try:
            make_handler(Service())(server_socket, ("local", 0), object())
        finally:
            server_socket.close()

    thread = threading.Thread(
        target=handle,
        daemon=True,
    )
    thread.start()
    try:
        client_socket.settimeout(2)
        client_socket.sendall(request)
        client_socket.shutdown(socket.SHUT_WR)
        response = b""
        while chunk := client_socket.recv(65536):
            response += chunk
    finally:
        client_socket.close()
        thread.join(timeout=2)
    head, body = response.split(b"\r\n\r\n", 1)
    status = int(head.split(b" ", 2)[1])
    return status, json.loads(body)


def get(path: str, token: str | None = None) -> tuple[int, dict]:
    authorization = f"Authorization: Bearer {token}\r\n" if token else ""
    return exchange(f"GET {path} HTTP/1.0\r\nHost: localhost\r\n{authorization}\r\n".encode())


def post(path: str, value: dict, token: str) -> tuple[int, dict]:
    body = json.dumps(value).encode()
    return exchange(
        f"POST {path} HTTP/1.0\r\nHost: localhost\r\n"
        f"Authorization: Bearer {token}\r\n"
        f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )


def test_health_is_public_and_api_requires_bearer_token():
    assert get("/healthz") == (200, {"status": "ok"})
    assert get("/v1/status") == (401, {"error": "unauthorized"})
    status, payload = get("/v1/status", "secret-token")
    assert status == 200
    assert payload["status"] == "ready"


def test_scan_accepts_get_and_post():
    status, payload = get("/v1/scan?since=1h&limit=5", "secret-token")
    assert status == 200
    assert payload["options"] == {"since": "1h", "limit": "5"}

    status, payload = post(
        "/v1/scan",
        {"since": "7d", "tag": "production"},
        "secret-token",
    )
    assert status == 200
    assert payload["options"]["tag"] == "production"


def test_server_requires_explicit_auth_choice(monkeypatch):
    monkeypatch.delenv("HEALER_SERVER_TOKEN", raising=False)
    monkeypatch.delenv("HEALER_ALLOW_UNAUTHENTICATED", raising=False)
    with pytest.raises(ConfigurationError, match="HEALER_SERVER_TOKEN"):
        ServerSettings.from_environment()

    settings = ServerSettings.from_environment(allow_unauthenticated=True)
    assert settings.allow_unauthenticated
