from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .errors import ConfigurationError, HealerError
from .repository_ingest import RepositoryRegistry

_MAX_BODY_BYTES = 64 * 1024


@dataclass(slots=True)
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8080
    token: str | None = None
    local_log: Path = Path("/data/runs.jsonl")
    repo_path: Path = Path(".")
    resolution_log: Path = Path("/data/resolutions.jsonl")
    repo_registry: Path = Path("/data/repositories")
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
            repo_path=Path(os.getenv("HEALER_REPO_PATH", ".")),
            resolution_log=Path(os.getenv("HEALER_RESOLUTION_LOG", "/data/resolutions.jsonl")),
            repo_registry=Path(os.getenv("HEALER_REPO_REGISTRY", "/data/repositories")),
            allow_unauthenticated=allowed,
        )


class HealerService:
    def __init__(
        self, capability: Any, *, token: str | None, settings: ServerSettings | None = None
    ) -> None:
        self.capability = capability
        self.token = token
        self.settings = settings or ServerSettings()

    @classmethod
    def initialize(cls, settings: ServerSettings) -> HealerService:
        import healer

        capability = healer.init(
            workflow_name=os.getenv("HEALER_WORKFLOW_NAME", "healer-server"),
            local_log=settings.local_log,
            provider=os.getenv("HEALER_PROVIDER") or None,
            model=os.getenv("HEALER_MODEL") or None,
        )
        return cls(capability, token=settings.token, settings=settings)

    def status(self) -> dict[str, Any]:
        return {"status": "ready", "capabilities": self.capability.to_dict()}

    def examples(self) -> dict[str, Any]:
        from .lab_runner import CATALOG

        return {"examples": [{"id": key, **value} for key, value in CATALOG.items()]}

    def run_example(self, options: dict[str, Any]) -> dict[str, Any]:
        from .lab_runner import run_lab

        example = options.get("example")
        if not isinstance(example, str):
            raise TypeError("example must be a catalog ID")
        return run_lab(example)

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

    def doctor(self, options: dict[str, Any]) -> dict[str, Any]:
        import healer

        repo_path = self.settings.repo_path
        user_id = _optional_string(options.get("user_id"))
        full_name = _optional_string(options.get("repository"))
        commit_sha = _optional_string(options.get("commit_sha"))
        if any((user_id, full_name, commit_sha)):
            if not all((user_id, full_name, commit_sha)):
                raise ValueError("user_id, repository, and commit_sha must be provided together")
            repo_path = RepositoryRegistry(self.settings.repo_registry).path_for(
                user_id, full_name, commit_sha
            )
            if repo_path is None:
                raise ValueError("repository checkout was not ingested")

        return healer.doctor(
            repo_path=repo_path,
            resolution_log=self.settings.resolution_log,
            since=str(options.get("since", "24h")),
            app_id=_optional_string(options.get("app_id")),
            session_id=_optional_string(options.get("session_id")),
            limit=_limit(options.get("limit", 100)),
        )

    def ingest_repository(self, options: dict[str, Any]) -> dict[str, Any]:
        return RepositoryRegistry(self.settings.repo_registry).ingest(
            user_id=str(options.get("user_id", "")),
            full_name=str(options.get("full_name", "")),
            commit_sha=str(options.get("commit_sha", "")),
            token=str(options.get("github_token", "")),
        )

    def propose(self, options: dict[str, Any]) -> dict[str, Any]:
        import healer

        from .models import Finding

        app_id = str(options.get("app_id", ""))
        finding_id = str(options.get("finding_id", ""))
        user_id = str(options.get("user_id", ""))
        full_name = str(options.get("repository", ""))
        commit_sha = str(options.get("commit_sha", ""))
        if not all((app_id, finding_id, user_id, full_name, commit_sha)):
            raise ValueError("agent, finding, and pinned repository are required")
        repo = RepositoryRegistry(self.settings.repo_registry).path_for(
            user_id, full_name, commit_sha
        )
        if repo is None:
            raise ValueError("repository checkout was not ingested")
        report = self.doctor({**options, "since": "30d", "limit": 1000})
        row = next((row for row in report["rows"] if row["finding"]["id"] == finding_id), None)
        if row is None:
            raise ValueError("finding was not found in this agent's observed traces")
        paths = list(dict.fromkeys(item["file"] for item in row["candidate_locations"]))
        if not paths:
            raise ValueError("finding has no candidate source file; map it before drafting a fix")
        model = healer.provider(
            "openai", model=os.getenv("OPENAI_MODEL") or os.getenv("HEALER_MODEL") or "gpt-5-mini"
        )
        proposal = healer.propose_fix(
            [Finding(**row["finding"])],
            repo_path=repo,
            allowed_files=paths,
            model=model,
            write_proposal=False,
        )
        return {
            "proposal": proposal.to_dict(),
            "validation": "not_run",
            "pull_request": None,
            "basis": "observed finding, candidate source, and possible static calls",
        }

    def record_resolution(self, options: dict[str, Any]) -> dict[str, Any]:
        import healer

        finding_id = str(options.get("finding_id", ""))
        if not any(
            row["finding"]["id"] == finding_id
            for row in self.doctor({"since": "30d", "limit": 1000})["rows"]
        ):
            raise ValueError("finding_id was not found in recent traces")
        return healer.record_resolution(
            finding_id,
            status=str(options.get("status", "")),
            note=str(options.get("note", "")),
            pr_url=_optional_string(options.get("pr_url")),
            path=self.settings.resolution_log,
        )


def make_handler(service: HealerService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SpectreHealer"

        def do_GET(self) -> None:
            route = urlparse(self.path)
            if route.path.startswith("/app/"):
                self._asset(route.path)
                return
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
            if route.path == "/v1/examples":
                self._json(HTTPStatus.OK, service.examples())
                return
            if route.path == "/v1/scan":
                options = {key: values[-1] for key, values in parse_qs(route.query).items()}
                self._scan(options)
                return
            if route.path == "/v1/doctor":
                options = {key: values[-1] for key, values in parse_qs(route.query).items()}
                self._doctor(options)
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

        def do_POST(self) -> None:
            route = urlparse(self.path)
            if not self._authorized():
                return
            if route.path not in {
                "/v1/scan",
                "/v1/resolutions",
                "/v1/repositories",
                "/v1/example-runs",
                "/v1/proposals",
            }:
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
            if route.path == "/v1/scan":
                self._scan(value)
            elif route.path == "/v1/example-runs":
                try:
                    self._json(HTTPStatus.OK, service.run_example(value))
                except (ImportError, TypeError, ValueError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            elif route.path == "/v1/proposals":
                try:
                    self._json(HTTPStatus.OK, service.propose(value))
                except (HealerError, TypeError, ValueError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            elif route.path == "/v1/repositories":
                try:
                    self._json(HTTPStatus.OK, service.ingest_repository(value))
                except (ValueError, OSError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            else:
                try:
                    self._json(HTTPStatus.OK, service.record_resolution(value))
                except (HealerError, ValueError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def _scan(self, options: dict[str, Any]) -> None:
            try:
                self._json(HTTPStatus.OK, service.scan(options))
            except (HealerError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def _doctor(self, options: dict[str, Any]) -> None:
            try:
                self._json(HTTPStatus.OK, service.doctor(options))
            except (HealerError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def _asset(self, path: str) -> None:
            name, content_type = {
                "/app/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
                "/app/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
            }.get(path, ("dashboard.html", "text/html; charset=utf-8"))
            body = files("healer").joinpath(name).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

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
