from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import ConfigurationError, ExternalToolError
from .models import ValidationResult


def open_pull_request(
    *,
    repo_path: str | Path,
    title: str,
    validation: ValidationResult,
    trace_ids: list[str],
    draft: bool = False,
) -> str:
    """Open a PR only through this explicit call and only for an accepted measured fix."""
    if not validation.accepted:
        raise ConfigurationError("Refusing to open a PR for a fix that did not pass validation.")
    if not shutil.which("gh"):
        raise ConfigurationError("GitHub CLI (gh) is required to open a pull request.")
    body = (
        "## Measured result\n\n"
        f"- Before: {validation.before.passed}/{validation.before.total}\n"
        f"- After: {validation.after.passed}/{validation.after.total}\n"
        f"- Trace IDs: {', '.join(trace_ids)}\n"
        f"- Cost before: {validation.before.cost_usd if validation.before.cost_usd is not None else 'TBD'}\n"
        f"- Cost after: {validation.after.cost_usd if validation.after.cost_usd is not None else 'TBD'}\n"
    )
    command = ["gh", "pr", "create", "--title", title, "--body", body]
    if draft:
        command.append("--draft")
    process = subprocess.run(command, cwd=repo_path, text=True, capture_output=True, check=False)
    if process.returncode:
        raise ExternalToolError(f"Could not open pull request: {process.stderr.strip()}")
    return process.stdout.strip()
