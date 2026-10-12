from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .models import Finding, RegressionCase, Score, Trace, ValidationResult
from .scanner import scan_traces


def findings_to_cases(findings: Iterable[Finding]) -> list[RegressionCase]:
    cases: list[RegressionCase] = []
    for finding in findings:
        source_input = finding.evidence.get("input")
        cases.append(
            RegressionCase(
                id=f"case-{finding.id}",
                finding_id=finding.id,
                check=finding.check,
                input=source_input,
                expected=f"No {finding.check} finding should be emitted.",
                trace_id=finding.trace_id,
            )
        )
    return cases


def seal_cases(cases: Iterable[RegressionCase], salt: str) -> tuple[list[RegressionCase], str]:
    sealed = [
        RegressionCase(
            id=case.id,
            finding_id=case.finding_id,
            check=case.check,
            input=case.input,
            expected=case.expected,
            trace_id=case.trace_id,
            sealed=True,
        )
        for case in cases
    ]
    digest = hashlib.sha256(
        (
            salt + json.dumps([case.to_dict() for case in sealed], sort_keys=True, default=repr)
        ).encode()
    ).hexdigest()
    return sealed, digest


@dataclass(slots=True)
class CaseResult:
    case_id: str
    passed: bool
    finding_checks: list[str]
    error: str | None = None


Runner = Callable[[Any], Trace]


def run_cases(cases: Iterable[RegressionCase], runner: Runner) -> tuple[Score, list[CaseResult]]:
    results: list[CaseResult] = []
    for case in cases:
        try:
            trace = runner(case.input)
            checks = [finding.check for finding in scan_traces([trace])]
            passed = case.check not in checks
            results.append(CaseResult(case.id, passed, checks))
        except Exception as exc:  # noqa: BLE001 - a case runner may be arbitrary user code
            results.append(CaseResult(case.id, False, [], f"{type(exc).__name__}: {exc}"))
    return Score.from_results([item.passed for item in results]), results


def validate_candidate(
    cases: list[RegressionCase],
    before_runner: Runner,
    after_runner: Runner,
    *,
    hidden_cases: list[RegressionCase] | None = None,
) -> ValidationResult:
    before, _ = run_cases(cases, before_runner)
    after, _ = run_cases(cases, after_runner)
    hidden_before = hidden_after = None
    if hidden_cases:
        hidden_before, _ = run_cases(hidden_cases, before_runner)
        hidden_after, _ = run_cases(hidden_cases, after_runner)
    visible_improved = (after.success_rate or 0.0) > (before.success_rate or 0.0)
    hidden_not_worse = not hidden_cases or (hidden_after.success_rate or 0.0) >= (
        hidden_before.success_rate or 0.0
    )
    accepted = visible_improved and hidden_not_worse and after.failed == 0
    if accepted:
        reason = "Visible failures are fixed, the suite is green, and hidden performance did not regress."
    elif not visible_improved:
        reason = "Rejected: measured visible success rate did not improve."
    elif after.failed:
        reason = "Rejected: at least one visible regression case still fails."
    else:
        reason = "Rejected: sealed test performance regressed."
    return ValidationResult(accepted, before, after, hidden_before, hidden_after, reason)
