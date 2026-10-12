"""Investigations preserve measured evidence and label inferred causes."""

import json

from healer.investigation import investigate_finding, source_context


def sample_row():
    return {
        "finding": {
            "id": "a" * 16,
            "check": "ignored_error",
            "trace_id": "trace-1",
            "span_id": "span-1",
            "reason": "Gateway error was followed by success",
        },
        "suggestion": "Gate the final answer on tool success.",
        "candidate_locations": [{"file": "agent.py", "line": 2}],
        "invocation_path": ["agent", "gateway"],
        "code_neighbors": [{"from": "agent.py::agent", "to": "agent.py::gateway"}],
    }


def test_rule_based_investigation_needs_no_model_or_repository():
    result = investigate_finding(sample_row(), None)
    assert result["model_status"] == "not_configured"
    assert result["evidence"]["trace_id"] == "trace-1"
    assert result["evidence"]["candidate_locations"] == []
    assert "Replay" in result["how_to_verify"]


def test_model_uses_bounded_source_but_cannot_change_evidence(tmp_path):
    (tmp_path / "agent.py").write_text("def gateway():\n    return 'Error: timeout'\n")
    captured = []

    def complete(prompt):
        captured.append(prompt)
        return json.dumps(
            {
                "likely_cause": "The success response ignores the timeout.",
                "suggested_fix": "Require a confirmed ledger result.",
                "how_to_verify": "Replay the timeout input and assert an unconfirmed answer.",
            }
        )

    result = investigate_finding(
        sample_row(),
        {"spans": [{"name": "gateway", "status": "ok", "output": "Error: timeout"}]},
        repo_path=tmp_path,
        complete=complete,
    )
    assert result["model_status"] == "used"
    assert result["evidence"]["trace_id"] == "trace-1"
    assert "def gateway" in captured[0]
    assert "untrusted data" in captured[0]
    assert "Require a confirmed ledger" in result["suggested_fix"]


def test_source_context_stays_inside_repository(tmp_path):
    (tmp_path / "agent.py").write_text("safe")
    assert source_context(tmp_path, [{"file": "../secret.py"}, {"file": "agent.py"}]) == {
        "agent.py": "safe"
    }


def test_model_accepts_fenced_json_response():
    response = {
        "likely_cause": "The success branch ignored the timeout.",
        "suggested_fix": "Require confirmation.",
        "how_to_verify": "Replay the timeout.",
    }
    result = investigate_finding(
        sample_row(), None, complete=lambda _: "```json\n" + json.dumps(response) + "\n```"
    )
    assert result["model_status"] == "used"
