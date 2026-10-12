from __future__ import annotations

from .checks import Check, run_checks
from .models import Finding, Trace
from .runtime import Runtime, get_runtime


def scan(
    *,
    since: str = "24h",
    tag: str | None = None,
    trace_id: str | None = None,
    limit: int = 100,
    checks: list[Check] | None = None,
    runtime: Runtime | None = None,
) -> list[Finding]:
    active = runtime or get_runtime()
    traces = active.traces(since=since, tag=tag, trace_id=trace_id, limit=limit)
    return scan_traces(traces, checks=checks)


def scan_traces(traces: list[Trace], checks: list[Check] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for trace in traces:
        for finding in run_checks(trace, traces, checks):
            if finding.id not in seen:
                seen.add(finding.id)
                findings.append(finding)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda item: (severity_order[item.severity], item.trace_id, item.check))
    return findings
