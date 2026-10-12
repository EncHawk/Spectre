"""Spectre checks for competitor research claims lacking a source."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from healer.checks import BUILTIN_CHECKS
from healer.models import Finding, Trace
from healer.scanner import scan_traces
from healer.store import LocalTraceStore


def competitor_evidence_check(trace: Trace, _: list[Trace]) -> list[Finding]:
    """Flag specific factual fields that need review before a lead is used."""
    if "competitor-research" not in trace.tags:
        return []
    root = next((span for span in trace.spans if span.parent_id is None), None)
    if root is None or not isinstance(root.output, dict):
        return []
    report = root.output
    findings: list[Finding] = []

    def check_fields(label: str, values: Any, evidence: Any, fields: tuple[str, ...]) -> None:
        if not isinstance(values, dict):
            return
        evidence = evidence if isinstance(evidence, dict) else {}
        for field in fields:
            if not values.get(field):
                findings.append(_finding(trace, root.id, label, field, "Missing research field"))
            elif not _has_source(evidence.get(field)):
                findings.append(_finding(trace, root.id, label, field, "Claim has no source URL"))

    check_fields(
        "subject",
        report.get("subject"),
        report.get("subject_evidence"),
        ("what_they_do", "product", "icp", "problem_solved"),
    )
    for index, lead in enumerate(report.get("leads") or []):
        if not isinstance(lead, dict):
            continue
        label = f"lead[{index}] {lead.get('name', 'unnamed')}"
        check_fields(
            label,
            lead,
            lead.get("evidence"),
            ("why_competitor", "what_they_do", "product", "icp", "problem_solved"),
        )
        for metric_index, metric in enumerate(lead.get("growth_metrics") or []):
            if not isinstance(metric, dict):
                continue
            if not _has_source(metric) or not metric.get("period") or not metric.get("value"):
                findings.append(
                    _finding(
                        trace,
                        root.id,
                        label,
                        f"growth_metrics[{metric_index}]",
                        "Growth number lacks a source, value, or reporting period",
                    )
                )
    return findings


def _has_source(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("sources"))


def _finding(trace: Trace, span_id: str, label: str, field: str, issue: str) -> Finding:
    fingerprint = f"{trace.id}:{label}:{field}:{issue}"
    return Finding(
        id=hashlib.sha256(fingerprint.encode()).hexdigest()[:16],
        check="competitor_evidence",
        reason=f"{label}.{field}: {issue}.",
        trace_id=trace.id,
        span_id=span_id,
        severity="medium",
        trace_url=trace.url,
        evidence={"company": label, "field": field},
    )


def main() -> None:
    local_traces = LocalTraceStore(".healer/runs.jsonl").list(
        since="24h", tags=["competitor-research"]
    )
    findings = scan_traces(local_traces, checks=[*BUILTIN_CHECKS, competitor_evidence_check])
    print(
        json.dumps(
            {"count": len(findings), "findings": [item.to_dict() for item in findings]}, indent=2
        )
    )


if __name__ == "__main__":
    main()
