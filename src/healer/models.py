from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Capability:
    send_traces: bool = False
    read_traces: bool = False
    send_detail: str = "not configured"
    read_detail: str = "not configured"
    local_fallback: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Span:
    id: str
    trace_id: str
    name: str
    kind: str = "INTERNAL"
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    status: str = "ok"
    input: Any = None
    output: Any = None
    error: str | None = None
    parent_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any], trace_id: str = "") -> Span:
        attrs = value.get("attributes") or value.get("metadata") or {}
        input_value = value.get("input", value.get("inputValue"))
        output_value = value.get("output", value.get("outputValue"))
        if isinstance(input_value, dict) and set(input_value) == {"value"}:
            input_value = input_value["value"]
        if isinstance(output_value, dict) and set(output_value) == {"value"}:
            output_value = output_value["value"]
        return cls(
            id=str(value.get("id") or value.get("spanId") or "unknown"),
            trace_id=str(value.get("traceId") or trace_id),
            name=str(value.get("name") or value.get("spanName") or "unnamed"),
            kind=str(
                value.get("kind") or value.get("spanKind") or value.get("spanType") or "INTERNAL"
            ).upper(),
            started_at=str(
                value.get("startedAt")
                or value.get("startTime")
                or value.get("started_at")
                or utc_now()
            ),
            ended_at=value.get("endedAt") or value.get("endTime") or value.get("ended_at"),
            status=str(value.get("status") or "ok").lower(),
            input=input_value,
            output=output_value,
            error=value.get("error") or value.get("errorMessage"),
            parent_id=value.get("parentId") or value.get("parentSpanId") or value.get("parent_id"),
            attributes=attrs if isinstance(attrs, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Trace:
    id: str
    name: str
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    status: str = "ok"
    spans: list[Span] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None
    url: str | None = None
    source: Literal["local", "neatlogs", "replay"] = "local"

    @classmethod
    def from_dict(cls, value: dict[str, Any], source: str = "neatlogs") -> Trace:
        trace_id = str(value.get("id") or value.get("traceId") or "unknown")
        raw_spans = value.get("spans") or []
        attrs = value.get("attributes") or value.get("metadata") or {}
        return cls(
            id=trace_id,
            name=str(
                value.get("name")
                or value.get("traceName")
                or value.get("workflowName")
                or "unnamed"
            ),
            started_at=str(
                value.get("startedAt")
                or value.get("startTime")
                or value.get("started_at")
                or utc_now()
            ),
            ended_at=(
                value.get("endedAt")
                or value.get("endTime")
                or value.get("completedAt")
                or value.get("ended_at")
            ),
            status=str(value.get("status") or "ok").lower(),
            spans=[Span.from_dict(s, trace_id) for s in raw_spans if isinstance(s, dict)],
            tags=[str(t) for t in (value.get("tags") or [])],
            attributes=attrs if isinstance(attrs, dict) else {},
            cost_usd=_float_or_none(
                value.get(
                    "costUsd", value.get("totalCostUsd", value.get("cost", value.get("cost_usd")))
                )
            ),
            url=value.get("url") or value.get("traceUrl"),
            source=source,  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


Severity = Literal["low", "medium", "high", "critical"]


@dataclass(slots=True)
class Finding:
    id: str
    check: str
    reason: str
    trace_id: str
    span_id: str | None
    severity: Severity
    trace_url: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RegressionCase:
    id: str
    finding_id: str
    check: str
    input: Any
    expected: str
    trace_id: str
    sealed: bool = False

    def to_dict(self, reveal: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if self.sealed and not reveal:
            value["input"] = "<sealed>"
        return value


@dataclass(slots=True)
class CauseGroup:
    id: str
    cause: str
    fix_layer: Literal["prompt", "tool", "rules"]
    finding_ids: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FixProposal:
    id: str
    summary: str
    diff: str
    files: list[str]
    finding_ids: list[str]
    status: Literal["proposed", "blocked", "accepted", "rejected"] = "proposed"
    reason: str | None = None
    branch: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Score:
    total: int
    passed: int
    failed: int
    success_rate: float | None
    cost_usd: float | None = None

    @classmethod
    def from_results(cls, results: list[bool], cost_usd: float | None = None) -> Score:
        passed = sum(results)
        return cls(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            success_rate=(passed / len(results)) if results else None,
            cost_usd=cost_usd,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    accepted: bool
    before: Score
    after: Score
    hidden_before: Score | None = None
    hidden_after: Score | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
