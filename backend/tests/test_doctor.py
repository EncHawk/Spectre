import subprocess

import pytest

import healer
from healer.doctor import _github_url, doctor, record_resolution
from healer.models import Span, Trace
from healer.runtime import get_runtime, reset_runtime


def test_session_identity_is_written_to_local_trace(tmp_path):
    reset_runtime()
    healer.init(local_log=tmp_path / "runs.jsonl")

    @healer.agent
    def run():
        return "ok"

    with healer.session("orders", "chat-42"):
        assert run() == "ok"
    trace = get_runtime().store.list(since="7d")[0]
    assert trace.attributes["app_id"] == "orders"
    assert trace.attributes["session_id"] == "chat-42"
    reset_runtime()


def test_doctor_joins_trace_to_tracked_ast_without_source_body(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "agent.py").write_text(
        "def search(query):\n    secret = 'api_key=never-persist-me'\n    return query\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "agent.py"], cwd=repo, check=True)
    span = Span("span", "trace", "search", kind="TOOL", input="q", status="error", error="failed")
    trace = Trace(
        "trace",
        "orders",
        spans=[span],
        status="error",
        attributes={"app_id": "orders", "session_id": "chat-42"},
    )

    class Runtime:
        def traces(self, **_):
            return [trace]

    result = doctor(repo_path=repo, runtime=Runtime(), app_id="orders", session_id="chat-42")
    assert result["trace_count"] == 1
    assert result["runs"][0]["spans"][0]["name"] == "search"
    assert result["runs"][0]["trace_id"] == "trace"
    assert result["finding_count"] >= 1
    row = next(row for row in result["rows"] if row["finding"]["check"] == "no_recovery")
    assert row["candidate_locations"][0]["file"] == "agent.py"
    assert row["candidate_locations"][0]["line"] == 1
    assert row["invocation_path"] == ["search"]
    assert "never-persist-me" not in str(result)
    assert "chat-42" in row["copy_to_agent"]
    record_resolution(
        row["finding"]["id"],
        status="investigating",
        note="reproduced locally",
        path=tmp_path / "resolutions.jsonl",
    )
    updated = doctor(
        repo_path=repo,
        runtime=Runtime(),
        resolution_log=tmp_path / "resolutions.jsonl",
    )
    assert (
        next(item for item in updated["rows"] if item["finding"]["id"] == row["finding"]["id"])[
            "resolution"
        ]["status"]
        == "investigating"
    )
    assert (
        len(
            next(item for item in updated["rows"] if item["finding"]["id"] == row["finding"]["id"])[
                "resolution_history"
            ]
        )
        == 1
    )


def test_resolution_history_is_append_only_and_validates_pr(tmp_path):
    path = tmp_path / "resolutions.jsonl"
    record_resolution("a" * 16, status="investigating", note="first", path=path)
    record_resolution(
        "a" * 16,
        status="resolved",
        note="token=secret-value",
        pr_url="https://github.com/acme/agent/pull/12",
        path=path,
    )
    contents = path.read_text()
    assert len(contents.splitlines()) == 2
    assert "secret-value" not in contents
    with pytest.raises(ValueError, match="GitHub pull request"):
        record_resolution("a" * 16, status="resolved", pr_url="https://evil.test/x", path=path)


def test_github_remote_normalization_rejects_embedded_credentials():
    assert _github_url("git@github.com:acme/agent.git") == "https://github.com/acme/agent"
    assert _github_url("https://github.com/acme/agent.git") == "https://github.com/acme/agent"
    assert _github_url("https://token@github.com/acme/agent.git") is None


def test_filtered_chat_uses_local_identity_when_remote_trace_lacks_it(tmp_path):
    local = Trace("local", "agent", attributes={"app_id": "support", "session_id": "chat-1"})
    remote = Trace("remote", "agent")

    class Store:
        def list(self, **_):
            return [local]

    class Runtime:
        store = Store()

        def traces(self, **_):
            return [remote]

    result = doctor(repo_path=tmp_path, runtime=Runtime(), app_id="support", session_id="chat-1")
    assert result["trace_count"] == 1
    assert result["rows"][0]["finding"]["trace_id"] == "local"
