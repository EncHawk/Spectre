from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .models import Finding, ValidationResult, utc_now


def build_report(
    findings: Iterable[Finding],
    *,
    validation: ValidationResult | None = None,
    proposal_id: str | None = None,
) -> dict:
    items = list(findings)
    return {
        "generated_at": utc_now(),
        "finding_count": len(items),
        "trace_ids": sorted({item.trace_id for item in items}),
        "findings": [item.to_dict() for item in items],
        "proposal_id": proposal_id,
        "validation": validation.to_dict() if validation else None,
        "cost_usd": {
            "before": validation.before.cost_usd if validation else "TBD",
            "after": validation.after.cost_usd if validation else "TBD",
        },
    }


def write_report(report: dict, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        target.write_text(json.dumps(report, indent=2) + "\n")
    else:
        target.write_text(_markdown(report))
    return target


def _markdown(report: dict) -> str:
    lines = [
        "# Healer report",
        "",
        f"Generated: {report['generated_at']}",
        f"Findings: {report['finding_count']}",
        f"Trace IDs: {', '.join(report['trace_ids']) or 'none'}",
        "",
        "## Findings",
        "",
    ]
    for item in report["findings"]:
        lines.append(
            f"- **{item['severity']} · {item['check']}** — {item['reason']} "
            f"(trace `{item['trace_id']}`, span `{item['span_id'] or 'n/a'}`)"
        )
    if not report["findings"]:
        lines.append("No findings.")
    lines.extend(["", "## Before / after", ""])
    validation = report.get("validation")
    if not validation:
        lines.append("Not measured yet (TBD).")
    else:
        lines.extend(
            [
                f"- Accepted: {validation['accepted']}",
                f"- Before: {validation['before']['passed']}/{validation['before']['total']}",
                f"- After: {validation['after']['passed']}/{validation['after']['total']}",
                f"- Decision: {validation['reason']}",
            ]
        )
    return "\n".join(lines) + "\n"
