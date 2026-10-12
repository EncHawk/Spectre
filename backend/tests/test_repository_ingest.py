from __future__ import annotations

import sqlite3
import subprocess

import pytest

from healer import repository_ingest
from healer.repository_ingest import RepositoryRegistry
from healer.server import HealerService, ServerSettings


def test_registry_fetches_pinned_commit_without_persisting_token(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    (source / "agent.py").write_text("def run():\n    return 1\n")
    subprocess.run(["git", "-C", str(source), "add", "agent.py"], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "initial"], check=True)
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()

    original = subprocess.run

    def local_git(command, **kwargs):
        if command[3:6] == ["remote", "add", "origin"]:
            command = [*command[:-1], str(source)]
        return original(command, **kwargs)

    monkeypatch.setattr(repository_ingest.subprocess, "run", local_git)
    registry = RepositoryRegistry(tmp_path / "cache")
    result = registry.ingest(user_id="google-123", full_name="example/agent", commit_sha=sha, token="secret-oauth-token")
    checkout = registry.path_for("google-123", "example/agent", sha)
    assert checkout is not None
    assert result["commit_sha"] == sha
    assert (checkout / "agent.py").exists()
    assert "secret-oauth-token" not in (checkout / ".git" / "config").read_text()
    assert registry.ingest(user_id="google-123", full_name="example/agent", commit_sha=sha, token="another-token") == result
    assert registry.path_for("other-user", "example/agent", sha) is None


def test_registry_rejects_invalid_identity(tmp_path):
    registry = RepositoryRegistry(tmp_path / "cache")
    with pytest.raises(ValueError, match="invalid repository identity"):
        registry.ingest(user_id="u", full_name="../../wrong", commit_sha="a" * 40, token="token")


def test_doctor_selects_registered_checkout(tmp_path, monkeypatch):
    import healer

    registry = RepositoryRegistry(tmp_path / "cache")
    checkout = registry.root / "checkout"
    checkout.mkdir()
    sha = "a" * 40
    with sqlite3.connect(registry.registry) as db:
        db.execute("INSERT INTO checkouts VALUES(?,?,?,?)", ("google-123", "example/agent", sha, str(checkout)))
    observed = {}

    def fake_doctor(**options):
        observed.update(options)
        return {"rows": []}

    monkeypatch.setattr(healer, "doctor", fake_doctor)
    service = HealerService(None, token="service", settings=ServerSettings(repo_registry=registry.root))
    assert service.doctor({"user_id": "google-123", "repository": "example/agent", "commit_sha": sha, "app_id": "orders"}) == {"rows": []}
    assert observed["repo_path"] == checkout
    assert observed["app_id"] == "orders"
    with pytest.raises(ValueError, match="not ingested"):
        service.doctor({"user_id": "other", "repository": "example/agent", "commit_sha": sha})
