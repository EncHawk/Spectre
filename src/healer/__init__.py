"""Spectre Healer: trace-driven QA and guarded repair for any Python agent."""

from __future__ import annotations

import functools
import inspect
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .adversarial import Fault, attack, inject_fault, variant_cases, variants
from .causes import group_causes
from .errors import ConfigurationError
from .fixes import apply_proposal, propose_fix
from .models import (
    Capability,
    CauseGroup,
    Finding,
    FixProposal,
    RegressionCase,
    Score,
    Span,
    Trace,
    ValidationResult,
)
from .providers import (
    Generation,
    Provider,
    configure_default_provider,
    create_provider,
    get_default_provider,
)
from .pull_request import open_pull_request
from .regression import findings_to_cases, run_cases, seal_cases, validate_candidate
from .report import build_report, write_report
from .runtime import Runtime, get_runtime, init_runtime
from .scanner import scan, scan_traces


def init(
    api_key: str | None = None,
    *,
    public_token: str | None = None,
    project_id: str | None = None,
    host: str | None = None,
    ingest_endpoint: str | None = None,
    workflow_name: str = "healer",
    local_log: str | Path = ".healer/runs.jsonl",
    provider: str | None = None,
    model: str | None = None,
    provider_api_key: str | None = None,
) -> Capability:
    """Initialize tracing/read capabilities and return what is actually available."""
    runtime = init_runtime(
        api_key,
        public_token=public_token,
        project_id=project_id,
        host=host,
        ingest_endpoint=ingest_endpoint,
        workflow_name=workflow_name,
        local_log=local_log,
    )
    provider_name = provider or os.getenv("HEALER_PROVIDER")
    if provider_name:
        try:
            configured = configure_default_provider(
                provider_name,
                model=model,
                api_key=provider_api_key,
            )
            configured.validate_setup()
            runtime.capability.model_generation = True
            runtime.capability.model_provider = configured.name
            runtime.capability.model_name = configured.model
            runtime.capability.model_detail = (
                f"{configured.name} SDK and local authentication configuration found"
            )
        except ConfigurationError as exc:
            runtime.capability.model_detail = (
                f"Model provider configuration failed: {type(exc).__name__}: {exc}"
            )
    else:
        runtime.capability.model_detail = (
            "Set HEALER_PROVIDER or pass provider= to enable model generation"
        )
    return runtime.capability


def provider(
    name: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    client: Any = None,
    **options: Any,
) -> Provider:
    """Create a provider adapter without changing the process-wide default."""
    return create_provider(name, model=model, api_key=api_key, client=client, **options)


def _lazy_instrument[F: Callable[..., Any]](
    target: F,
    *,
    name: str | None,
    kind: str,
    tags: tuple[str, ...] = (),
) -> F:
    """Resolve the runtime when called, allowing decorators before healer.init()."""
    lock = threading.Lock()
    cached_runtime: Runtime | None = None
    cached_wrapper: Callable[..., Any] | None = None

    def resolve() -> Callable[..., Any]:
        nonlocal cached_runtime, cached_wrapper
        runtime = get_runtime()
        if cached_runtime is not runtime or cached_wrapper is None:
            with lock:
                if cached_runtime is not runtime or cached_wrapper is None:
                    cached_wrapper = runtime.instrument(target, name=name, kind=kind, tags=tags)
                    cached_runtime = runtime
        return cached_wrapper

    if inspect.iscoroutinefunction(target):

        @functools.wraps(target)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await resolve()(*args, **kwargs)

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(target)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        return resolve()(*args, **kwargs)

    return sync_wrapper  # type: ignore[return-value]


def agent[F: Callable[..., Any]](
    function: F | None = None,
    *,
    name: str | None = None,
    tags: tuple[str, ...] = (),
) -> F | Callable[[F], F]:
    """Trace any sync or async agent function as a root AGENT span."""

    def decorate(target: F) -> F:
        return _lazy_instrument(target, name=name, kind="AGENT", tags=tags)

    return decorate(function) if function else decorate


def tool[F: Callable[..., Any]](
    function: F | None = None, *, name: str | None = None
) -> F | Callable[[F], F]:
    """Trace an agent tool and nest it under the current agent run."""

    def decorate(target: F) -> F:
        return _lazy_instrument(target, name=name, kind="TOOL")

    return decorate(function) if function else decorate


trace = agent


def init_runtime_for_demo(local_log: str | Path) -> Runtime:
    """Initialize a deterministic local-only runtime used by the packaged demo."""
    return init_runtime(
        api_key=None,
        public_token=None,
        project_id=None,
        workflow_name="healer-demo",
        local_log=local_log,
    )


__all__ = [
    "Capability",
    "CauseGroup",
    "Fault",
    "Finding",
    "FixProposal",
    "Generation",
    "Provider",
    "RegressionCase",
    "Runtime",
    "Score",
    "Span",
    "Trace",
    "ValidationResult",
    "agent",
    "apply_proposal",
    "attack",
    "build_report",
    "findings_to_cases",
    "get_default_provider",
    "group_causes",
    "init",
    "init_runtime_for_demo",
    "inject_fault",
    "open_pull_request",
    "propose_fix",
    "provider",
    "run_cases",
    "scan",
    "scan_traces",
    "seal_cases",
    "tool",
    "trace",
    "validate_candidate",
    "variant_cases",
    "variants",
    "write_report",
]
