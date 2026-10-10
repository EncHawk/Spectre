"""Spectre Healer: trace-driven QA and guarded repair for any Python agent."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .adversarial import Fault, attack, inject_fault, variant_cases, variants
from .causes import group_causes
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
) -> Capability:
    """Initialize tracing/read capabilities and return what is actually available."""
    return init_runtime(
        api_key,
        public_token=public_token,
        project_id=project_id,
        host=host,
        ingest_endpoint=ingest_endpoint,
        workflow_name=workflow_name,
        local_log=local_log,
    ).capability


def agent[F: Callable[..., Any]](
    function: F | None = None,
    *,
    name: str | None = None,
    tags: tuple[str, ...] = (),
) -> F | Callable[[F], F]:
    """Trace any sync or async agent function as a root AGENT span."""

    def decorate(target: F) -> F:
        return get_runtime().instrument(target, name=name, kind="AGENT", tags=tags)  # type: ignore[return-value]

    return decorate(function) if function else decorate


def tool[F: Callable[..., Any]](
    function: F | None = None, *, name: str | None = None
) -> F | Callable[[F], F]:
    """Trace an agent tool and nest it under the current agent run."""

    def decorate(target: F) -> F:
        return get_runtime().instrument(target, name=name, kind="TOOL")  # type: ignore[return-value]

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
    "group_causes",
    "init",
    "init_runtime_for_demo",
    "inject_fault",
    "open_pull_request",
    "propose_fix",
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
