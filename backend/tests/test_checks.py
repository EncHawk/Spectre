from healer.checks import run_checks
from healer.models import Span, Trace
from healer.scanner import scan_traces


def trace_with(*spans, status="ok", cost=None, trace_id="t"):
    return Trace(id=trace_id, name="agent", status=status, spans=list(spans), cost_usd=cost)


def span(identifier, name, kind="TOOL", **kwargs):
    return Span(id=identifier, trace_id="t", name=name, kind=kind, **kwargs)


def checks(trace, corpus=None):
    return {item.check for item in run_checks(trace, corpus or [trace])}


def test_repeated_tool_calls():
    root = span("r", "agent", "AGENT", output="done")
    calls = [span(str(i), "search", input={"q": "x"}, parent_id="r") for i in range(3)]
    assert "repeated_tool_calls" in checks(trace_with(root, *calls))


def test_different_tool_inputs_are_not_repeat():
    root = span("r", "agent", "AGENT", output="done")
    calls = [span(str(i), "search", input={"q": str(i)}, parent_id="r") for i in range(3)]
    assert "repeated_tool_calls" not in checks(trace_with(root, *calls))


def test_ignored_error_and_no_recovery():
    root = span("r", "agent", "AGENT", output="confident answer")
    failed = span("f", "search", status="error", error="timeout", parent_id="r")
    found = checks(trace_with(root, failed, status="error"))
    assert {"ignored_error", "no_recovery"}.issubset(found)


def test_successful_retry_is_recovery():
    root = span("r", "agent", "AGENT", output="answer")
    failed = span("f", "search", status="error", error="timeout", parent_id="r")
    recovered = span("s", "search", output="ok", parent_id="r")
    assert "ignored_error" not in checks(trace_with(root, failed, recovered))


def test_failed_run_without_answer_is_not_ignored_error():
    root = span("r", "agent", "AGENT", status="error", error="timeout", output=None)
    failed = span("f", "search", status="error", error="timeout", parent_id="r")
    assert "ignored_error" not in checks(trace_with(root, failed, status="error"))


def test_research_about_failures_is_not_a_tool_error():
    root = span("r", "agent", "AGENT", output={"summary": "Agent failure diagnosis"})
    tool = span("s", "research", output={"product": "Detects agent failures"}, parent_id="r")
    assert "ignored_error" not in checks(trace_with(root, tool))


def test_loop_detection():
    root = span("r", "agent", "AGENT", output="answer")
    items = []
    for index, name in enumerate(["a", "b"] * 3):
        items.append(span(str(index), name, parent_id="r"))
    assert "loop" in checks(trace_with(root, *items))


def test_empty_answer():
    assert "empty_answer" in checks(trace_with(span("r", "agent", "AGENT", output="")))


def test_answered_without_lookup_and_claim_without_source():
    root = span(
        "r",
        "agent",
        "AGENT",
        input="What is the latest price? Cite sources",
        output="The current price is definitely one hundred dollars in the market.",
    )
    found = checks(trace_with(root))
    assert "answered_without_lookup" in found
    assert "claim_without_source" in found


def test_lookup_avoids_lookup_findings():
    root = span("r", "agent", "AGENT", input="latest news", output="See https://example.com")
    tool = span("s", "search", parent_id="r", output="result")
    found = checks(trace_with(root, tool))
    assert "answered_without_lookup" not in found
    assert "claim_without_source" not in found


def test_cost_spike_requires_five_samples():
    corpus = [trace_with(cost=1, trace_id=str(i)) for i in range(5)]
    expensive = trace_with(span("r", "agent", "AGENT", output="ok"), cost=5, trace_id="x")
    corpus.append(expensive)
    assert "cost_spike" in checks(expensive, corpus)


def test_scan_deduplicates_and_orders():
    root = span("r", "agent", "AGENT", output="")
    findings = scan_traces([trace_with(root)])
    assert len({finding.id for finding in findings}) == len(findings)
