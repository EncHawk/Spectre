from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import healer

from .models import Span, Trace
from .report import build_report, write_report
from .sponsors import write_business_inputs


def _trace_for(query: Any, repeats: int) -> Trace:
    trace = Trace(id=f"demo-{repeats}", name="research_agent", tags=["demo"])
    root = Span(
        id=f"root-{repeats}",
        trace_id=trace.id,
        name="research_agent",
        kind="AGENT",
        input=query,
        output="A sourced answer.",
    )
    trace.spans.append(root)
    for index in range(repeats):
        trace.spans.append(
            Span(
                id=f"tool-{repeats}-{index}",
                trace_id=trace.id,
                name="search",
                kind="TOOL",
                parent_id=root.id,
                input={"query": query},
                output=[{"title": "Measured demo result"}],
            )
        )
    return trace


def run_demo(output_dir: str | Path = "evidence/demo") -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    runtime = healer.init_runtime_for_demo(target / "runs.jsonl")

    @healer.tool(name="search")
    def search(query: str) -> list[dict[str, str]]:
        return [{"title": "Measured demo result", "url": "https://example.invalid/evidence"}]

    @healer.agent(tags=("demo",))
    def research_agent(query: str) -> str:
        results = []
        for _ in range(3):  # intentionally flawed: identical tool request repeated
            results.extend(search(query))
        return f"Found {len(results)} results."

    research_agent("Find the latest evidence about agent reliability")
    findings = healer.scan(since="1h", tag="demo", runtime=runtime)
    causes = healer.group_causes(findings)
    cases = healer.findings_to_cases(findings)
    hidden, sealed_digest = healer.seal_cases(cases, "demo-only-salt")

    diff = """diff --git a/examples/research_agent/agent.py b/examples/research_agent/agent.py
--- a/examples/research_agent/agent.py
+++ b/examples/research_agent/agent.py
@@ -11,7 +11,7 @@ def research_agent(query: str) -> str:
-    for _ in range(3):
+    for _ in range(1):
         results.extend(search(query))
"""

    def proposal_model(_: str) -> str:
        return json.dumps({"summary": "Deduplicate identical searches", "diff": diff})

    proposal = healer.propose_fix(
        findings,
        repo_path=".",
        allowed_files=["examples/research_agent/agent.py"],
        complete=proposal_model,
    )
    validation = healer.validate_candidate(
        cases,
        lambda query: _trace_for(query, 3),
        lambda query: _trace_for(query, 1),
        hidden_cases=hidden,
    )
    report = build_report(findings, validation=validation, proposal_id=proposal.id)
    report_path = write_report(report, target / "report.json")
    write_report(report, target / "report.md")
    write_business_inputs(
        "business/inputs.json",
        baseline_success_rate=validation.before.success_rate,
        healed_success_rate=validation.after.success_rate,
        baseline_cost_usd=None,
        healed_cost_usd=None,
        evaluated_runs=validation.before.total
        + (validation.hidden_before.total if validation.hidden_before else 0),
    )
    return {
        "capability": runtime.capability.to_dict(),
        "findings": len(findings),
        "causes": len(causes),
        "proposal": proposal.to_dict(),
        "validation": validation.to_dict(),
        "sealed_digest": sealed_digest,
        "report": str(report_path),
    }
