from __future__ import annotations

import contextvars
import functools
import inspect
import os
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from .errors import AuthenticationError, HealerError, PermissionDeniedError
from .models import Capability, Span, Trace, utc_now
from .neatlogs_client import NeatlogsClient
from .privacy import Redactor
from .store import LocalTraceStore

P = ParamSpec("P")
R = TypeVar("R")
_active_trace: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "healer_active_trace", default=None
)
_active_span: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "healer_active_span", default=None
)
_active_identity: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "healer_active_identity", default=None
)


@contextmanager
def session(app_id: str, session_id: str):
    """Attach a caller-owned app and chat/session ID to traces in this context."""
    if not app_id or not session_id:
        raise ValueError("app_id and session_id must be non-empty")
    token = _active_identity.set((app_id, session_id))
    try:
        yield
    finally:
        _active_identity.reset(token)


@dataclass(slots=True)
class Settings:
    ingest_key: str | None
    ingest_endpoint: str | None
    read_token: str | None
    project_id: str | None
    host: str
    workflow_name: str
    local_log: Path


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redactor = Redactor()
        self.store = LocalTraceStore(settings.local_log, self.redactor)
        self.client: NeatlogsClient | None = None
        self._neatlogs: Any = None
        self.capability = Capability()
        self._lock = threading.Lock()
        self._configure()

    def _configure(self) -> None:
        if self.settings.ingest_key:
            try:
                import neatlogs  # type: ignore[import-not-found]

                options = {
                    "api_key": self.settings.ingest_key,
                    "workflow_name": self.settings.workflow_name,
                }
                if self.settings.ingest_endpoint:
                    options["endpoint"] = self.settings.ingest_endpoint
                neatlogs.init(**options)
                self._neatlogs = neatlogs
                self.capability.send_traces = True
                self.capability.send_detail = "Neatlogs ingest initialized"
            except ImportError:
                self.capability.send_detail = (
                    "NEATLOGS_API_KEY is set, but the optional 'neatlogs' package is not installed"
                )
            except Exception as exc:  # noqa: BLE001 - vendor exceptions are not stable
                self.capability.send_detail = (
                    f"Neatlogs ingest initialization failed: {type(exc).__name__}"
                )
        else:
            self.capability.send_detail = "NEATLOGS_API_KEY is not set; recording locally"

        if self.settings.read_token and self.settings.project_id:
            self.client = NeatlogsClient(
                self.settings.read_token,
                self.settings.project_id,
                self.settings.host,
            )
            try:
                self.client.probe()
                self.capability.read_traces = True
                self.capability.read_detail = "Neatlogs Public API read access confirmed"
            except (AuthenticationError, PermissionDeniedError, HealerError) as exc:
                self.capability.read_detail = str(exc)
        elif self.settings.read_token:
            self.capability.read_detail = "NEATLOGS_PROJECT_ID is required for Public API reads"
        else:
            self.capability.read_detail = (
                "NEATLOGS_TOKEN is not set; use a project-bound service-account token "
                "with context:read and observability:read"
            )

    def traces(
        self,
        *,
        since: str = "24h",
        tag: str | None = None,
        trace_id: str | None = None,
        limit: int = 100,
    ) -> list[Trace]:
        if self.capability.read_traces and self.client:
            return self.client.list_traces(since=since, tag=tag, trace_id=trace_id, limit=limit)
        local = self.store.list(since=since, tags=[tag] if tag else None)
        if trace_id:
            local = [trace for trace in local if trace.id == trace_id]
        return local[-limit:]

    def instrument(
        self,
        function: Callable[P, R],
        *,
        name: str | None = None,
        kind: str = "AGENT",
        tags: tuple[str, ...] = (),
    ) -> Callable[P, R]:
        if inspect.iscoroutinefunction(function):
            wrapped = self._instrument_async(function, name=name, kind=kind, tags=tags)
        else:
            wrapped = self._instrument_sync(function, name=name, kind=kind, tags=tags)
        if self._neatlogs is not None:
            # The vendor decorator creates the Neatlogs span while our wrapper always
            # keeps the redacted local fallback needed when Public API reads are absent.
            # Neatlogs 1.x accepts CHAIN, not LLM. Preserve LLM in the local trace.
            vendor_kind = "CHAIN" if kind.upper() == "LLM" else kind.upper()
            wrapped = self._neatlogs.span(kind=vendor_kind, name=name or function.__name__)(wrapped)
        return wrapped  # type: ignore[return-value]

    def _start(
        self, function: Callable[..., Any], name: str | None, kind: str, tags: tuple[str, ...]
    ):
        parent_trace = _active_trace.get()
        trace = parent_trace or Trace(
            id=uuid.uuid4().hex,
            name=name or function.__name__,
            tags=list(tags),
            attributes={"healer.instrumented": True},
        )
        if parent_trace is None and (identity := _active_identity.get()) is not None:
            trace.attributes.update({"app_id": identity[0], "session_id": identity[1]})
        span = Span(
            id=uuid.uuid4().hex,
            trace_id=trace.id,
            name=name or function.__name__,
            kind=kind.upper(),
            parent_id=_active_span.get(),
        )
        trace.spans.append(span)
        trace_token = _active_trace.set(trace)
        span_token = _active_span.set(span.id)
        return parent_trace is None, trace, span, trace_token, span_token

    def _finish(
        self, root: bool, trace: Trace, span: Span, trace_token: Any, span_token: Any
    ) -> None:
        span.ended_at = utc_now()
        _active_span.reset(span_token)
        _active_trace.reset(trace_token)
        if root:
            trace.ended_at = span.ended_at
            if span.status == "error":
                trace.status = "error"
            with self._lock:
                self.store.append(trace)

    def _instrument_sync(
        self,
        function: Callable[P, R],
        *,
        name: str | None,
        kind: str,
        tags: tuple[str, ...],
    ) -> Callable[P, R]:
        @functools.wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            root, trace, span, trace_token, span_token = self._start(function, name, kind, tags)
            span.input = self.redactor.redact({"args": args, "kwargs": kwargs})
            try:
                result = function(*args, **kwargs)
                span.output = self.redactor.redact(result)
                return result
            except Exception as exc:
                span.status = "error"
                span.error = self.redactor.redact_text(f"{type(exc).__name__}: {exc}")
                raise
            finally:
                self._finish(root, trace, span, trace_token, span_token)

        return wrapped

    def _instrument_async(
        self,
        function: Callable[P, Any],
        *,
        name: str | None,
        kind: str,
        tags: tuple[str, ...],
    ) -> Callable[P, Any]:
        @functools.wraps(function)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> Any:
            root, trace, span, trace_token, span_token = self._start(function, name, kind, tags)
            span.input = self.redactor.redact({"args": args, "kwargs": kwargs})
            try:
                result = await function(*args, **kwargs)
                span.output = self.redactor.redact(result)
                return result
            except Exception as exc:
                span.status = "error"
                span.error = self.redactor.redact_text(f"{type(exc).__name__}: {exc}")
                raise
            finally:
                self._finish(root, trace, span, trace_token, span_token)

        return wrapped


_runtime: Runtime | None = None


def init_runtime(
    api_key: str | None = None,
    *,
    public_token: str | None = None,
    project_id: str | None = None,
    host: str | None = None,
    ingest_endpoint: str | None = None,
    workflow_name: str = "healer",
    local_log: str | Path = ".healer/runs.jsonl",
) -> Runtime:
    global _runtime
    ingest_key = api_key or os.getenv("NEATLOGS_API_KEY")
    # Some hackathon keys may be service tokens; explicit token wins, then env, then the supplied key.
    read_token = public_token or os.getenv("NEATLOGS_TOKEN") or api_key
    settings = Settings(
        ingest_key=ingest_key,
        ingest_endpoint=ingest_endpoint or os.getenv("NEATLOGS_INGEST_ENDPOINT"),
        read_token=read_token,
        project_id=project_id or os.getenv("NEATLOGS_PROJECT_ID"),
        host=host or os.getenv("NEATLOGS_HOST", "https://app.neatlogs.com"),
        workflow_name=workflow_name,
        local_log=Path(local_log),
    )
    _runtime = Runtime(settings)
    return _runtime


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = init_runtime()
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None
