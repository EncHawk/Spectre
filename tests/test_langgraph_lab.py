"""Exercise complete LangGraph runs through Spectre as a black box."""

from __future__ import annotations

import healer
from healer.lab_runner import run_lab


def test_checkout_red_team_exposes_false_success_and_repair(tmp_path, monkeypatch):
    monkeypatch.delenv("NEATLOGS_API_KEY", raising=False)
    runtime = healer.init_runtime_for_demo(tmp_path / "runs.jsonl")
    report = run_lab("checkout_support")
    assert report["case_count"] == 3
    assert report["before_passed"] < report["after_passed"] == 3
    pressure = next(item for item in report["cases"] if item["case"] == "pressure")
    assert not pressure["before"]["passed"]
    assert pressure["after"]["passed"]
    assert "ignored_error" in pressure["before"]["checks"]
    assert len(runtime.store.list(since="1h")) == 6
    assert any(span["name"] == "fallback_ledger" for span in pressure["after"]["spans"])


def test_research_red_team_finds_contract_failure_beyond_generic_checks(tmp_path, monkeypatch):
    monkeypatch.delenv("NEATLOGS_API_KEY", raising=False)
    healer.init_runtime_for_demo(tmp_path / "runs.jsonl")
    report = run_lab("research_brief")
    assert report["before_passed"] == 1
    assert report["after_passed"] == 3
    injected = next(item for item in report["cases"] if item["case"] == "injection")
    assert not injected["before"]["passed"]
    assert injected["after"]["passed"]
    assert "plan_research" in [span["name"] for span in injected["before"]["spans"]]
    # A retrieval span exists, so the generic citation heuristic does not catch
    # this evidence laundering. The domain contract does.
    assert "claim_without_source" not in injected["before"]["checks"]
