from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

from .causes import group_causes
from .errors import ExternalToolError, HealerError, UnsafePatchError
from .models import Finding, FixProposal
from .privacy import Redactor
from .providers import Provider, get_default_provider

Completion = Callable[[str], str]
_DIFF_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def propose_fix(
    findings: Iterable[Finding],
    *,
    repo_path: str | Path,
    allowed_files: Iterable[str] | None = None,
    complete: Completion | None = None,
    model: Provider | None = None,
    write_proposal: bool = True,
) -> FixProposal:
    items = list(findings)
    causes = group_causes(items)
    identifier = hashlib.sha256(":".join(sorted(f.id for f in items)).encode()).hexdigest()[:12]
    if not items:
        return FixProposal(
            id=f"fix-{identifier}",
            summary="No findings to fix.",
            diff="",
            files=[],
            finding_ids=[],
            status="blocked",
            reason="A fix proposal requires at least one measured finding.",
        )
    prompt = _build_prompt(items, causes, Path(repo_path), allowed_files)
    try:
        completion = complete or (model or get_default_provider()).complete
        response = _extract_json(completion(prompt))
        diff = str(response.get("diff", ""))
        summary = str(response.get("summary", "Proposed fix"))
        files = validate_diff(diff, allowed_files)
        proposal = FixProposal(
            id=f"fix-{identifier}",
            summary=summary,
            diff=diff,
            files=files,
            finding_ids=[f.id for f in items],
        )
    except Exception as exc:  # noqa: BLE001 - model/provider callbacks have no shared exception type
        proposal = FixProposal(
            id=f"fix-{identifier}",
            summary="Fix generation is blocked until a configured model is available.",
            diff="",
            files=[],
            finding_ids=[f.id for f in items],
            status="blocked",
            reason=f"{type(exc).__name__}: {exc}",
        )
    if write_proposal:
        target = Path(repo_path) / ".healer" / "proposals" / f"{proposal.id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(Redactor().redact(proposal.to_dict()), indent=2) + "\n")
    return proposal


def _extract_json(text: str) -> dict[str, object]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0]
        stripped = stripped.removeprefix("json\n")
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise HealerError("The model did not return the required JSON object.") from exc
    if not isinstance(value, dict):
        raise HealerError("The model returned JSON, but not an object.")
    return value


def validate_diff(diff: str, allowed_files: Iterable[str] | None = None) -> list[str]:
    if not diff.strip():
        raise UnsafePatchError("The proposed diff is empty.")
    files = _DIFF_FILE.findall(diff)
    if not files:
        raise UnsafePatchError("The proposal is not a unified diff with '+++ b/<path>' headers.")
    allowed = {PurePosixPath(path).as_posix() for path in (allowed_files or [])}
    for filename in files:
        path = PurePosixPath(filename)
        if path.is_absolute() or ".." in path.parts or filename == "/dev/null":
            raise UnsafePatchError(f"Patch path is outside the repository: {filename}")
        if allowed and path.as_posix() not in allowed:
            raise UnsafePatchError(
                f"Patch touches {filename}, which is outside the allowed file set."
            )
    return sorted(set(files))


def apply_proposal(
    proposal: FixProposal,
    *,
    repo_path: str | Path,
    branch: str,
    commit: bool = False,
) -> FixProposal:
    """Explicitly mutate git state. Callers must opt into this function and branch."""
    if proposal.status != "proposed" or not proposal.diff:
        raise UnsafePatchError("Only a non-empty proposed fix can be applied.")
    repository = Path(repo_path)
    _git(repository, "switch", "-c", branch)
    process = subprocess.run(
        ["git", "apply", "--index", "--whitespace=error", "-"],
        cwd=repository,
        input=proposal.diff,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise ExternalToolError(f"git apply failed: {process.stderr.strip()}")
    proposal.branch = branch
    if commit:
        _git(repository, "commit", "-m", f"fix: {proposal.summary[:60]}")
    return proposal


def _git(repository: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args], cwd=repository, text=True, capture_output=True, check=False
    )
    if process.returncode:
        raise ExternalToolError(f"git {' '.join(args)} failed: {process.stderr.strip()}")
    return process.stdout.strip()


def _build_prompt(findings, causes, repo_path: Path, allowed_files) -> str:
    safe = Redactor()
    payload = safe.redact(
        {
            "findings": [finding.to_dict() for finding in findings],
            "causes": [cause.to_dict() for cause in causes],
            "repo": repo_path.name,
            "allowed_files": list(allowed_files or []),
        }
    )
    return (
        "You are repairing an AI agent from measured trace failures. Return ONLY a JSON object "
        "with keys summary and diff. diff must be a valid unified git diff. Make the smallest "
        "change at the identified layer. Never invent measurements, trace IDs, or files.\n"
        + json.dumps(payload, indent=2)
    )
