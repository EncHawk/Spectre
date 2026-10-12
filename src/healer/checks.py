from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from .models import Finding, Span, Trace

Check = Callable[[Trace, list[Trace]], Iterable[Finding]]
_FAILURE_WORDS = re.compile(r"(?i)\b(error|failed|failure|exception|timed? out|rate limit)\b")
_RECOVERY_WORDS = re.compile(r"(?i)\b(retry|recover|fallback|backoff|alternative)\b")
_LOOKUP_INPUT = re.compile(
    r"(?i)\b(latest|current|today|news|price|source|cite|research|look up)\b"
)
_CITATION = re.compile(r"https?://|\[[0-9]+\]|\b(source|according to|citation)s?\b", re.IGNORECASE)


def run_checks(
    trace: Trace, corpus: list[Trace], checks: list[Check] | None = None
) -> list[Finding]:
    selected = checks or BUILTIN_CHECKS
    findings: list[Finding] = []
    for check in selected:
        findings.extend(check(trace, corpus))
    return findings


def repeated_tool_calls(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    calls: Counter[str] = Counter()
    last: tuple[str, str] | None = None
    consecutive = 0
    for span in trace.spans:
        if span.kind != "TOOL":
            continue
        signature = (span.name, _stable(span.input))
        calls["|".join(signature)] += 1
        consecutive = consecutive + 1 if signature == last else 1
        last = signature
        if consecutive >= 3:
            yield _finding(
                trace,
                span,
                "repeated_tool_calls",
                f"Tool {span.name!r} was called at least {consecutive} times consecutively with the same input.",
                "high",
                {"tool": span.name, "repeat_count": consecutive, "input": span.input},
            )
            return


def ignored_errors(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    for index, span in enumerate(trace.spans):
        failed_output = isinstance(span.output, str) and _FAILURE_WORDS.match(span.output.lstrip())
        failed = span.status == "error" or span.error or failed_output
        if not failed:
            continue
        later = trace.spans[index + 1 :]
        recovered = any(
            candidate.status == "ok"
            and (
                candidate.name == span.name
                or _RECOVERY_WORDS.search(candidate.name + " " + _text(candidate.attributes))
            )
            for candidate in later
        )
        root_output = trace.spans[0].output if trace.spans else None
        if not recovered and root_output is not None and _text(root_output).strip():
            yield _finding(
                trace,
                span,
                "ignored_error",
                f"Failure in {span.name!r} was followed by an answer without a recorded recovery.",
                "high",
                {"error": span.error or span.output, "later_span_count": len(later)},
            )


def no_recovery(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    failed = [s for s in trace.spans if s.status == "error" or s.error]
    if failed and trace.status == "error":
        span = failed[-1]
        yield _finding(
            trace,
            span,
            "no_recovery",
            f"Run ended after {span.name!r} failed; no fallback or successful retry was recorded.",
            "medium",
            {"error": span.error},
        )


def loops(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    sequence = [f"{s.kind}:{s.name}" for s in trace.spans]
    for width in range(2, min(6, len(sequence) // 2 + 1)):
        for start in range(len(sequence) - width * 2 + 1):
            pattern = sequence[start : start + width]
            repeats = 1
            cursor = start + width
            while sequence[cursor : cursor + width] == pattern:
                repeats += 1
                cursor += width
            if repeats >= 3:
                span = trace.spans[start]
                yield _finding(
                    trace,
                    span,
                    "loop",
                    f"The span sequence {pattern!r} repeated {repeats} times.",
                    "high",
                    {"pattern": pattern, "repeat_count": repeats},
                )
                return


def cost_spikes(trace: Trace, corpus: list[Trace]) -> Iterable[Finding]:
    costs = [item.cost_usd for item in corpus if item.cost_usd is not None and item.cost_usd >= 0]
    if trace.cost_usd is None or len(costs) < 5:
        return
    baseline = statistics.median(costs)
    if baseline > 0 and trace.cost_usd > baseline * 3:
        yield _finding(
            trace,
            None,
            "cost_spike",
            f"Trace cost ${trace.cost_usd:.6f} exceeded 3x the corpus median ${baseline:.6f}.",
            "medium",
            {"cost_usd": trace.cost_usd, "median_cost_usd": baseline, "sample_size": len(costs)},
        )


def empty_answers(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    if not trace.spans:
        yield _finding(
            trace, None, "empty_answer", "Trace has no spans or recorded answer.", "high", {}
        )
        return
    root = next((s for s in trace.spans if s.parent_id is None), trace.spans[0])
    output = root.output
    if output is None or (isinstance(output, str) and not output.strip()):
        yield _finding(
            trace,
            root,
            "empty_answer",
            f"Root span {root.name!r} returned an empty answer.",
            "high",
            {"output": output},
        )


def unsupported_claims(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    root = next(
        (s for s in trace.spans if s.parent_id is None), trace.spans[0] if trace.spans else None
    )
    if not root:
        return
    output = _text(root.output)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", output) if len(s.split()) >= 8]
    evidence_spans = [s for s in trace.spans if s.kind in {"RETRIEVER", "TOOL"}]
    asks_for_sources = _LOOKUP_INPUT.search(_text(root.input))
    if sentences and asks_for_sources and not evidence_spans and not _CITATION.search(output):
        yield _finding(
            trace,
            root,
            "claim_without_source",
            "The answer makes substantive claims for a source-sensitive request without a citation or evidence span.",
            "high",
            {"sentence_count": len(sentences), "input": root.input},
        )


def answered_without_lookup(trace: Trace, _: list[Trace]) -> Iterable[Finding]:
    root = next(
        (s for s in trace.spans if s.parent_id is None), trace.spans[0] if trace.spans else None
    )
    if not root or not _LOOKUP_INPUT.search(_text(root.input)):
        return
    has_lookup = any(s.kind in {"TOOL", "RETRIEVER"} for s in trace.spans if s.id != root.id)
    if _text(root.output).strip() and not has_lookup:
        yield _finding(
            trace,
            root,
            "answered_without_lookup",
            "A time-sensitive or source-seeking request was answered without a tool or retrieval step.",
            "high",
            {"input": root.input},
        )


BUILTIN_CHECKS: list[Check] = [
    repeated_tool_calls,
    ignored_errors,
    no_recovery,
    loops,
    cost_spikes,
    empty_answers,
    unsupported_claims,
    answered_without_lookup,
]


def _finding(
    trace: Trace,
    span: Span | None,
    check: str,
    reason: str,
    severity: str,
    evidence: dict[str, Any],
) -> Finding:
    fingerprint = f"{trace.id}:{span.id if span else '-'}:{check}"
    identifier = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return Finding(
        id=identifier,
        check=check,
        reason=reason,
        trace_id=trace.id,
        span_id=span.id if span else None,
        severity=severity,  # type: ignore[arg-type]
        trace_url=trace.url,
        evidence=evidence,
    )


def _stable(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=repr)
    except (TypeError, ValueError):
        return repr(value)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=repr)
    except (TypeError, ValueError):
        return repr(value)
