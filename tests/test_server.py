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

    def doctor(self, options):
        return {"trace_count": 0, "finding_count": 0, "rows": [], "options": options}

    def record_resolution(self, options):
        return {"finding_id": options["finding_id"], "status": options["status"]}

    def ingest_repository(self, options):
        return {"full_name": options["full_name"], "indexed": True}

    def examples(self):
        return {"examples": [{"id": "checkout_support"}]}

    def run_example(self, options):
        return {"example": options["example"], "before_passed": 1, "after_passed": 3}

    def propose(self, options):
        return {"proposal": {"status": "proposed"}, "finding_id": options["finding_id"]}


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


def test_doctor_and_resolution_routes_require_token():
    assert get("/v1/doctor") == (401, {"error": "unauthorized"})
    status, payload = get("/v1/doctor?app_id=orders&session_id=chat-42", "secret-token")
    assert status == 200
    assert payload["options"] == {"app_id": "orders", "session_id": "chat-42"}
    status, payload = post(
        "/v1/resolutions", {"finding_id": "a" * 16, "status": "investigating"}, "secret-token"
    )
    assert status == 200
    assert payload["status"] == "investigating"


def test_repository_ingest_requires_service_token():
    body = {"full_name": "example/agent", "commit_sha": "a" * 40}
    assert get("/v1/repositories") == (401, {"error": "unauthorized"})
    status, payload = post("/v1/repositories", body, "secret-token")
    assert status == 200
    assert payload == {"full_name": "example/agent", "indexed": True}


def test_example_catalog_and_run_require_service_token():
    assert get("/v1/examples") == (401, {"error": "unauthorized"})
    assert post("/v1/example-runs", {"example": "checkout_support"}, "wrong") == (
        401,
        {"error": "unauthorized"},
    )
    assert get("/v1/examples", "secret-token")[1]["examples"][0]["id"] == "checkout_support"
    status, payload = post("/v1/example-runs", {"example": "checkout_support"}, "secret-token")
    assert status == 200
    assert payload["after_passed"] == 3


def test_proposal_route_requires_service_token():
    body = {"finding_id": "a" * 16}
    assert post("/v1/proposals", body, "wrong") == (401, {"error": "unauthorized"})
    status, payload = post("/v1/proposals", body, "secret-token")
    assert status == 200
    assert payload["finding_id"] == body["finding_id"]


def test_server_requires_explicit_auth_choice(monkeypatch):
    monkeypatch.delenv("HEALER_SERVER_TOKEN", raising=False)
    monkeypatch.delenv("HEALER_ALLOW_UNAUTHENTICATED", raising=False)
    with pytest.raises(ConfigurationError, match="HEALER_SERVER_TOKEN"):
        ServerSettings.from_environment()

    settings = ServerSettings.from_environment(allow_unauthenticated=True)
    assert settings.allow_unauthenticated
