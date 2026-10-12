"""Static code context is explicit about what can be inferred."""

import subprocess

from healer.code_graph import build_code_graph
from healer.fixes import propose_fix
from healer.models import Finding


def test_static_calls_and_grounded_proposal(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "agent.py"
    source.write_text("def verify():\n    return False\n\ndef run():\n    return verify()\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "agent.py"], check=True)
    graph = build_code_graph(tmp_path)
    assert {edge["from"] + " -> " + edge["to"] for edge in graph["edges"]} == {
        "agent.py::run -> agent.py::verify"
    }
    captured = []
    finding = Finding("a" * 16, "ignored_error", "run claimed success", "t", "s", "high")
    proposal = propose_fix(
        [finding],
        repo_path=tmp_path,
        allowed_files=["agent.py"],
        complete=lambda prompt: captured.append(prompt) or '{"summary":"blocked","diff":""}',
        write_proposal=False,
    )
    assert proposal.status == "blocked"
    assert "def verify()" in captured[0]
    assert "agent.py::run" in captured[0]
    assert "Static call edges are hypotheses" in captured[0]
