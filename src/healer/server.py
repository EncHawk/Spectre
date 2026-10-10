from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .errors import ConfigurationError, HealerError

_MAX_BODY_BYTES = 64 * 1024


@dataclass(slots=True)
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8080
    token: str | None = None
    local_log: Path = Path("/data/runs.jsonl")
    allow_unauthenticated: bool = False

    @classmethod
    def from_environment(
        cls,
        *,
        host: str | None = None,
        port: int | None = None,
        allow_unauthenticated: bool = False,
    ) -> ServerSettings:
        configured_port = port if port is not None else int(os.getenv("HEALER_PORT", "8080"))
        token = os.getenv("HEALER_SERVER_TOKEN") or None
        allowed = allow_unauthenticated or os.getenv(
            "HEALER_ALLOW_UNAUTHENTICATED", ""
        ).lower() in {"1", "true", "yes"}
        if not token and not allowed:
            raise ConfigurationError(
                "Set HEALER_SERVER_TOKEN before serving, or explicitly pass "
                "--allow-unauthenticated for a trusted local network."
            )
        return cls(
            host=host or os.getenv("HEALER_HOST", "0.0.0.0"),
            port=configured_port,
            token=token,
            local_log=Path(os.getenv("HEALER_LOCAL_LOG", "/data/runs.jsonl")),
            allow_unauthenticated=allowed,
        )


class HealerService:
    def __init__(self, capability: Any, *, token: str | None) -> None:
        self.capability = capability
        self.token = token

    @classmethod
    def initialize(cls, settings: ServerSettings) -> HealerService:
        import healer

        capability = healer.init(
            workflow_name=os.getenv("HEALER_WORKFLOW_NAME", "healer-server"),
            local_log=settings.local_log,
            provider=os.getenv("HEALER_PROVIDER") or None,
            model=os.getenv("HEALER_MODEL") or None,
        )
        return cls(capability, token=settings.token)

    def status(self) -> dict[str, Any]:
        return {"status": "ready", "capabilities": self.capability.to_dict()}

    def scan(self, options: dict[str, Any]) -> dict[str, Any]:
        import healer

        findings = healer.scan(
            since=str(options.get("since", "24h")),
            tag=_optional_string(options.get("tag")),
            trace_id=_optional_string(options.get("trace_id")),
            limit=_limit(options.get("limit", 100)),
        )
        return {
            "count": len(findings),
            "findings": [finding.to_dict() for finding in findings],
        }


def make_handler(service: HealerService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SpectreHealer"

        def do_GET(self) -> None:
            route = urlparse(self.path)
            if route.path == "/healthz":
                self._json(HTTPStatus.OK, {"status": "ok"})
                return
            if route.path == "/readyz":
                self._json(HTTPStatus.OK, {"status": "ready"})
                return
            if not self._authorized():
                return
            if route.path == "/v1/status":
                self._json(HTTPStatus.OK, service.status())
                return
            if route.path == "/v1/scan":
                options = {key: values[-1] for key, values in parse_qs(route.query).items()}
                self._scan(options)
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

        def do_POST(self) -> None:
            route = urlparse(self.path)
            if not self._authorized():
                return
            if route.path != "/v1/scan":
                self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > _MAX_BODY_BYTES:
                    self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
                    return
                value = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(value, dict):
                    raise TypeError("body must be a JSON object")
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._scan(value)

        def _scan(self, options: dict[str, Any]) -> None:
            try:
                self._json(HTTPStatus.OK, service.scan(options))
            except (HealerError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def _authorized(self) -> bool:
            if service.token is None:
                return True
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {service.token}"
            if hmac.compare_digest(supplied, expected):
                return True
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", "Bearer")
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            body = b'{"error":"unauthorized"}'
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return False

        def _json(self, status: HTTPStatus, value: dict[str, Any]) -> None:
            body = json.dumps(value, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            # Avoid logging query values; traces contain the useful, redacted diagnostics.
            return

    return Handler


def serve(
    *,
    host: str | None = None,
    port: int | None = None,
    allow_unauthenticated: bool = False,
) -> None:
    settings = ServerSettings.from_environment(
        host=host,
        port=port,
        allow_unauthenticated=allow_unauthenticated,
    )
    service = HealerService.initialize(settings)
    server = ThreadingHTTPServer((settings.host, settings.port), make_handler(service))
    print(f"Spectre Healer listening on http://{settings.host}:{settings.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _optional_string(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _limit(value: Any) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    return parsed
