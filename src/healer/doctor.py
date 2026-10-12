"""Read-only trace and repository context for the observability dashboard."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import threading
from pathlib import Path
from urllib.parse import quote, urlparse

from .causes import group_causes
from .code_graph import build_code_graph, neighbors
from .models import Finding, Trace, utc_now
from .privacy import Redactor
from .runtime import Runtime, get_runtime
from .scanner import scan_traces

_RESOLUTION_LOCK = threading.Lock()
_NEXT_STEPS = {
    "repeated_tool_calls": "Add a repeat-call guard and stop or vary the request after the limit.",
    "loop": "Set a bounded iteration limit for this agent path.",
    "ignored_error": "Gate the final answer on tool success or a recorded fallback.",
    "no_recovery": "Add a tested retry or fallback for the failed tool.",
    "empty_answer": "Require a non-empty result and handle missing output explicitly.",
    "claim_without_source": "Require retrieved evidence or a citation before making this claim.",
    "answered_without_lookup": "Route source-sensitive requests through a lookup step.",
    "cost_spike": "Set a run budget and inspect the steps that consumed it.",
}


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={repo}", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _github_url(remote: str | None) -> str | None:
    if not remote:
        return None
    match = re.fullmatch(r"git@github\.com:([\w.-]+)/([\w.-]+?)(?:\.git)?", remote)
    if match:
        return f"https://github.com/{match[1]}/{match[2]}"
    parsed = urlparse(remote)
    if parsed.scheme == "https" and parsed.hostname == "github.com" and not parsed.username:
        path = parsed.path.strip("/").removesuffix(".git")
        if re.fullmatch(r"[\w.-]+/[\w.-]+", path):
            return f"https://github.com/{path}"
    return None


def _code_index(repo: Path) -> tuple[dict[str, list[dict]], dict]:
    root = repo.resolve()
    commit = _git(root, "rev-parse", "HEAD")
    remote = _github_url(_git(root, "remote", "get-url", "origin"))
    tracked = _git(root, "ls-files", "--", "*.py") or ""
    index: dict[str, list[dict]] = {}
    files = 0
    indexed_bytes = 0
    for relative in tracked.splitlines():
        if files >= 500:
            break
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        size = path.stat().st_size
        if size > 1_000_000 or indexed_bytes + size > 20_000_000:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError):
            continue
        files += 1
        indexed_bytes += size

        def visit(nodes: list[ast.stmt], prefix: str = "", filename: str = relative) -> None:
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f"{prefix}.{node.name}" if prefix else node.name
                    location = {"symbol": name, "file": filename, "line": node.lineno}
                    if remote and commit:
                        location["url"] = (
                            f"{remote}/blob/{commit}/{quote(filename, safe='/')}#L{node.lineno}"
                        )
                    index.setdefault(node.name, []).append(location)
                    if isinstance(node, ast.ClassDef):
                        visit(node.body, name, filename)

        visit(tree.body)
    return index, {
        "path": str(root),
        "github_url": remote,
        "commit": commit,
        "indexed_files": files,
        "indexed_bytes": indexed_bytes,
    }


def _identity(trace: Trace) -> tuple[str, str]:
    attributes = trace.attributes
    return str(attributes.get("app_id") or trace.name), str(
        attributes.get("session_id") or trace.id
    )


def _locations(finding: Finding, trace: Trace, index: dict[str, list[dict]]) -> list[dict]:
    span = next((item for item in trace.spans if item.id == finding.span_id), None)
    candidates = [span.name] if span else []
    candidates.append(trace.name)
    matches: list[dict] = []
    for candidate in candidates:
        symbol = candidate.rsplit(".", 1)[-1]
        for location in index.get(symbol, []):
            if location not in matches:
                matches.append(location)
        if matches:
            break
    return matches[:5]


def _invocation_path(finding: Finding, trace: Trace) -> list[str]:
    spans = {span.id: span for span in trace.spans}
    current = spans.get(finding.span_id) if finding.span_id else None
    path: list[str] = []
    while current is not None and len(path) < 50:
        path.append(current.name)
        current = spans.get(current.parent_id)
    return list(reversed(path))


def _resolutions(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    result: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
                if isinstance(event, dict) and isinstance(event.get("finding_id"), str):
                    result.setdefault(event["finding_id"], []).append(event)
            except (json.JSONDecodeError, TypeError):
                continue
    return result


def record_resolution(
    finding_id: str,
    *,
    status: str,
    note: str = "",
    pr_url: str | None = None,
    path: str | Path = ".healer/resolutions.jsonl",
) -> dict:
    """Append an explicit, redacted resolution event; never creates a PR."""
    if not re.fullmatch(r"[a-f0-9]{16}", finding_id):
        raise ValueError("finding_id must be a scanner finding ID")
    if status not in {"investigating", "proposed", "validated", "resolved", "rejected"}:
        raise ValueError("invalid resolution status")
    if len(note) > 2000:
        raise ValueError("note must be at most 2000 characters")
    if pr_url is not None:
        parsed = urlparse(pr_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or not re.fullmatch(r"/[\w.-]+/[\w.-]+/pull/\d+/?", parsed.path)
            or parsed.username
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("pr_url must be a GitHub pull request URL")
    event = {
        "finding_id": finding_id,
        "status": status,
        "note": Redactor().redact_text(note),
        "pr_url": pr_url,
        "recorded_at": utc_now(),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _RESOLUTION_LOCK, target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    return event


def doctor(
    *,
    repo_path: str | Path = ".",
    since: str = "24h",
    app_id: str | None = None,
    session_id: str | None = None,
    limit: int = 100,
    resolution_log: str | Path = ".healer/resolutions.jsonl",
    runtime: Runtime | None = None,
) -> dict:
    """Join observed failures with candidate AST symbols and local resolution history."""
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    active = runtime or get_runtime()
    traces = active.traces(since=since, limit=limit)
    # Vendor traces may omit SDK-owned session attributes. Prefer the local,
    # redacted record for a specifically requested chat when it exists.
    if (app_id or session_id) and hasattr(active, "store"):
        local = active.store.list(since=since)
        matching_local = [
            trace
            for trace in local
            if (app_id is None or _identity(trace)[0] == app_id)
            and (session_id is None or _identity(trace)[1] == session_id)
        ]
        if matching_local:
            traces = matching_local[-limit:]
    selected = [
        trace
        for trace in traces
        if (app_id is None or _identity(trace)[0] == app_id)
        and (session_id is None or _identity(trace)[1] == session_id)
    ]
    findings = scan_traces(selected)
    trace_by_id = {trace.id: trace for trace in selected}
    index, repository = _code_index(Path(repo_path))
    graph = build_code_graph(Path(repo_path))
    repository["code_graph"] = graph
    resolutions = _resolutions(Path(resolution_log))
    redactor = Redactor()
    rows = []
    for finding in findings:
        trace = trace_by_id[finding.trace_id]
        app, session = _identity(trace)
        cause = group_causes([finding])[0]
        suggestion = _NEXT_STEPS.get(finding.check, cause.rationale)
        location = _locations(finding, trace, index)
        invocation_path = _invocation_path(finding, trace)
        related_calls = neighbors(graph, location)
        history = resolutions.get(finding.id, [])
        resolution = history[-1] if history else None
        code_refs = ", ".join(f"{item['file']}:{item['line']}" for item in location) or "unmapped"
        handoff = (
            f"Investigate Spectre finding {finding.id} in {repository['github_url'] or repository['path']} "
            f"at commit {repository['commit'] or 'unknown'}. App: {app}; session: {session}; "
            f"trace: {finding.trace_id}; span: {finding.span_id or 'n/a'}. "
            f"Observed: {finding.reason} Suggested check: {suggestion} "
            f"Candidate code: {code_refs}. "
            f"Observed invocation path: {' -> '.join(invocation_path) or 'unavailable'}. "
            f"Possible static call edges: {json.dumps(related_calls)}. "
            "Verify the root cause, make a minimal fix, run relevant regression tests, "
            "and open a PR only after validation."
        )
        rows.append(
            redactor.redact(
                {
                    "finding": finding.to_dict(),
                    "app_id": app,
                    "session_id": session,
                    "agent": trace.name,
                    "trace_status": trace.status,
                    "trace_started_at": trace.started_at,
                    "suggestion": suggestion,
                    "suggestion_basis": "deterministic check; code location is a name match",
                    "candidate_locations": location,
                    "invocation_path": invocation_path,
                    "code_neighbors": related_calls,
                    "resolution": resolution,
                    "resolution_history": history,
                    "copy_to_agent": handoff,
                }
            )
        )
    return {
        "generated_at": utc_now(),
        "repository": repository,
        "trace_count": len(selected),
        "finding_count": len(rows),
        "rows": rows,
        "runs": [
            {
                "trace_id": trace.id,
                "session_id": _identity(trace)[1],
                "name": redactor.redact_text(trace.name),
                "status": trace.status,
                "source": trace.source,
                "started_at": trace.started_at,
                "trace_url": trace.url,
                "spans": [
                    {
                        "id": span.id,
                        "parent_id": span.parent_id,
                        "name": redactor.redact_text(span.name),
                        "kind": span.kind,
                        "status": span.status,
                        "input": str(redactor.redact(span.input))[:1000],
                        "output": str(redactor.redact(span.output))[:1000],
                        "error": redactor.redact_text(span.error) if span.error else None,
                    }
                    for span in trace.spans[:100]
                ],
                "spans_truncated": len(trace.spans) > 100,
            }
            for trace in selected
        ],
    }
