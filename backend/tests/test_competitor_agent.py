"""Exercise the actual LangGraph flow with deterministic Parallel responses."""

import json
from types import SimpleNamespace

import pytest

import healer
from plus_usage.agent import build_agent, normalize_website
from plus_usage.checks import competitor_evidence_check


class FakeTasks:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(run_id=f"run-{len(self.created)}")

    def result(self, run_id, *, api_timeout):
        if run_id == "run-1":
            content = {
                "name": "Acme",
                "what_they_do": "Agent observability",
                "product": "Agent trace analysis",
                "icp": "AI teams",
                "problem_solved": "Finding broken agent runs",
            }
            basis = [
                {
                    "field": "product",
                    "citations": [{"url": "https://acme.test/product"}],
                    "confidence": "high",
                }
            ]
        elif run_id == "run-2":
            content = {
                "name": "Unrelated",
                "website": "https://unrelated.test",
                "is_competitor": False,
                "why_competitor": "Different market",
                "what_they_do": "Payments",
                "product": "Checkout",
                "icp": "Stores",
                "problem_solved": "Payments",
                "growth_metrics": [],
                "growth_unknowns": [],
            }
            basis = []
        else:
            content = {
                "name": "Rival",
                "website": "https://rival.test",
                "is_competitor": True,
                "why_competitor": "Agent trace analysis for AI teams",
                "what_they_do": "Agent observability",
                "product": "Trace dashboard",
                "icp": "AI teams",
                "problem_solved": "Finding broken agent runs",
                "growth_metrics": [
                    {
                        "metric": "customers",
                        "value": "120",
                        "period": "2026 Q2",
                        "context": "Paid customers",
                    },
                    {
                        "metric": "revenue",
                        "value": "$9m",
                        "period": "2026",
                        "context": "Unverified",
                    },
                ],
                "growth_unknowns": ["Revenue growth rate"],
            }
            basis = [
                {
                    "field": "why_competitor",
                    "citations": [{"url": "https://rival.test/product"}],
                    "confidence": "high",
                },
                {
                    "field": "growth_metrics.0.value",
                    "citations": [{"url": "https://rival.test/news"}],
                    "confidence": "medium",
                },
            ]
        return SimpleNamespace(output={"content": content, "basis": basis})


class FakeParallel:
    def __init__(self):
        self.task_run = FakeTasks()
        self.beta = SimpleNamespace(findall=SimpleNamespace(entity_search=self.entity_search))

    def entity_search(self, **kwargs):
        assert kwargs["entity_type"] == "companies"
        assert kwargs["match_limit"] >= 5
        return SimpleNamespace(
            entities=[
                SimpleNamespace(
                    name="Acme",
                    url="https://linkedin.com/company/acme",
                    description="Name: Acme | Website Url: https://acme.test | Self",
                ),
                SimpleNamespace(
                    name="Unrelated",
                    url="https://platform.tracxn.com/company/unrelated",
                    description="Name: Unrelated | Website Url: https://unrelated.test | Payments",
                ),
                SimpleNamespace(
                    name="Rival",
                    url="https://platform.tracxn.com/company/rival",
                    description="Name: Rival | Website Url: https://rival.test | Tracing",
                ),
            ]
        )


def test_graph_finds_competitor_and_keeps_only_sourced_growth(tmp_path):
    healer.init(local_log=tmp_path / "runs.jsonl")
    parallel = FakeParallel()
    report = build_agent(parallel)("acme.test", 1)

    assert report["website"] == "https://acme.test"
    assert report["candidates_found"] == 2
    assert [lead["name"] for lead in report["leads"]] == ["Rival"]
    assert report["leads"][0]["growth_metrics"] == [
        {
            "metric": "customers",
            "value": "120",
            "period": "2026 Q2",
            "context": "Paid customers",
            "sources": ["https://rival.test/news"],
            "confidence": "medium",
        }
    ]
    assert len(parallel.task_run.created) == 3
    assert "platform.tracxn.com" not in parallel.task_run.created[1]["input"]
    trace = json.loads((tmp_path / "runs.jsonl").read_text().splitlines()[0])
    assert trace["name"] == "run"
    assert {span["kind"] for span in trace["spans"]} == {"AGENT", "TOOL"}
    findings = healer.scan(
        since="24h", tag="competitor-research", checks=[competitor_evidence_check]
    )
    assert any("product" in finding.reason for finding in findings)


def test_rejects_non_web_urls_and_credentials():
    for value in ("file:///etc/passwd", "https://user:pass@example.com"):
        try:
            normalize_website(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted unsafe URL: {value}")


def test_spectre_flags_failed_parallel_call(tmp_path):
    healer.init(local_log=tmp_path / "runs.jsonl")

    class FailingTasks:
        def create(self, **kwargs):
            raise RuntimeError("Parallel research failed")

    parallel = SimpleNamespace(task_run=FailingTasks())
    with pytest.raises(RuntimeError, match="Parallel research failed"):
        build_agent(parallel)("acme.test", 1)

    findings = healer.scan(since="24h", tag="competitor-research")
    assert "no_recovery" in {finding.check for finding in findings}


def test_openai_ranking_omits_unsupported_temperature(tmp_path, monkeypatch):
    healer.init(local_log=tmp_path / "runs.jsonl")
    options = []

    class FakeModel:
        def complete(self, prompt, **kwargs):
            options.append(kwargs)
            return '["https://rival.test"]'

    monkeypatch.setattr(healer, "provider", lambda *args, **kwargs: FakeModel())
    report = build_agent(FakeParallel(), openai_model="gpt-test")("acme.test", 1)

    assert options[0]["temperature"] is None
    assert report["leads"][0]["name"] == "Rival"
