import json
from types import SimpleNamespace

import pytest

from healer.adversarial import Fault, attack, inject_fault, variants
from healer.causes import group_causes
from healer.errors import ConfigurationError, UnsafePatchError
from healer.fixes import propose_fix, validate_diff
from healer.models import Finding, Span, Trace
from healer.providers import configure_default_provider, reset_default_provider
from healer.regression import findings_to_cases, seal_cases, validate_candidate
from healer.replay import Recorder, Replayer
from healer.report import build_report, write_report
from healer.sponsors import write_business_inputs


def finding():
    return Finding("f", "repeated_tool_calls", "repeat", "t", "s", "high", evidence={"input": "q"})


def trace(repeats):
    root = Span("r", "t", "agent", kind="AGENT", input="q", output="ok")
    spans = [root] + [
        Span(str(i), "t", "search", kind="TOOL", parent_id="r", input="q") for i in range(repeats)
    ]
    return Trace("t", "agent", spans=spans)


def test_findings_to_cases_and_sealing():
    cases = findings_to_cases([finding()])
    sealed, digest = seal_cases(cases, "salt")
    assert cases[0].input == "q"
    assert sealed[0].to_dict(reveal=False)["input"] == "<sealed>"
    assert len(digest) == 64


def test_cause_group_selects_rules():
    group = group_causes([finding()])[0]
    assert group.fix_layer == "rules"


def test_validation_accepts_clear_improvement():
    cases = findings_to_cases([finding()])
    result = validate_candidate(cases, lambda _: trace(3), lambda _: trace(1), hidden_cases=cases)
    assert result.accepted
    assert result.before.success_rate == 0
    assert result.after.success_rate == 1


def test_validate_diff_file_boundary():
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    assert validate_diff(diff, ["a.py"]) == ["a.py"]
    with pytest.raises(UnsafePatchError):
        validate_diff(diff, ["b.py"])


def test_propose_fix_with_injected_model(tmp_path):
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    proposal = propose_fix(
        [finding()],
        repo_path=tmp_path,
        allowed_files=["a.py"],
        complete=lambda _: json.dumps({"summary": "fix", "diff": diff}),
    )
    assert proposal.status == "proposed"
    assert (tmp_path / ".healer" / "proposals" / f"{proposal.id}.json").exists()


def test_propose_fix_uses_configured_default_provider(tmp_path):
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n"

    class Responses:
        def create(self, **_):
            return SimpleNamespace(
                output_text=json.dumps({"summary": "provider fix", "diff": diff}),
                usage=None,
            )

    configure_default_provider(
        "openai",
        model="gpt-test",
        client=SimpleNamespace(responses=Responses()),
    )
    try:
        proposal = propose_fix(
            [finding()],
            repo_path=tmp_path,
            allowed_files=["a.py"],
        )
    finally:
        reset_default_provider()

    assert proposal.status == "proposed"
    assert proposal.summary == "provider fix"


def test_fault_injection_and_variants():
    broken = inject_fault(lambda: "ok", Fault("empty"))
    assert broken() is None
    assert broken() == "ok"
    assert len(variants(" hello   world? ")) == 5


def test_attacker_must_be_different_family():
    with pytest.raises(ConfigurationError):
        attack("prompt", agent_model_family="nova", attacker_model_family="nova", complete=str)


def test_record_and_replay(tmp_path):
    recorder = Recorder()
    tool = recorder.wrap("double", lambda value: value * 2)
    assert tool(3) == 6
    path = tmp_path / "replay.json"
    recorder.save(path)
    replay = Replayer.load(path)
    assert replay.tool("double")(999) == 6


def test_report_and_business_keep_unmeasured_as_tbd(tmp_path):
    report = build_report([finding()])
    path = write_report(report, tmp_path / "report.md")
    assert "Not measured yet (TBD)" in path.read_text()
    inputs = write_business_inputs(
        tmp_path / "inputs.json",
        baseline_success_rate=None,
        healed_success_rate=1.0,
        baseline_cost_usd=None,
        healed_cost_usd=None,
        evaluated_runs=1,
    )
    assert inputs["baseline_success_rate"] == "TBD"
    assert inputs["pricing"] == "TBD"
