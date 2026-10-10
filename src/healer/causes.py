from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable

from .models import CauseGroup, Finding

_LAYERS = {
    "repeated_tool_calls": ("rules", "The orchestration loop lacks a repeat-call guard."),
    "loop": ("rules", "The orchestration loop lacks a bounded stopping condition."),
    "ignored_error": ("tool", "Tool failure handling does not gate the final response."),
    "no_recovery": ("tool", "The tool path has no successful retry or fallback."),
    "empty_answer": ("prompt", "The response contract does not require a non-empty answer."),
    "claim_without_source": ("prompt", "The prompt does not enforce evidence-backed claims."),
    "answered_without_lookup": (
        "rules",
        "Routing rules allow source-sensitive answers without retrieval.",
    ),
    "cost_spike": ("rules", "Budget and iteration limits are not enforced."),
}


def group_causes(findings: Iterable[Finding]) -> list[CauseGroup]:
    grouped: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for finding in findings:
        layer, rationale = _LAYERS.get(
            finding.check, ("rules", "The failure is best contained by an explicit runtime rule.")
        )
        grouped[(layer, rationale)].append(finding)
    result: list[CauseGroup] = []
    for (layer, rationale), members in grouped.items():
        checks = sorted({member.check for member in members})
        cause = ", ".join(checks)
        identifier = hashlib.sha256((layer + cause).encode()).hexdigest()[:12]
        result.append(
            CauseGroup(
                id=f"cause-{identifier}",
                cause=cause,
                fix_layer=layer,  # type: ignore[arg-type]
                finding_ids=[member.id for member in members],
                rationale=rationale,
            )
        )
    return sorted(result, key=lambda item: item.id)
