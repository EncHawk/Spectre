from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError, ExternalToolError
from .models import ValidationResult
from .runtime import Runtime, get_runtime


@dataclass(slots=True)
class SuggestionTrial:
    suggestion_id: str
    accepted: bool
    reason: str
    validation: dict[str, Any] | None = None


def test_neatlogs_suggestions(
    test: Callable[[dict[str, Any]], ValidationResult],
    *,
    runtime: Runtime | None = None,
    limit: int = 50,
) -> list[SuggestionTrial]:
    """Test pending suggestions locally; never changes their server-side state."""
    active = runtime or get_runtime()
    if not active.client or not active.capability.read_traces:
        raise ConfigurationError("Neatlogs Public API read access is required for fix suggestions.")
    trials: list[SuggestionTrial] = []
    for suggestion in active.client.list_fix_suggestions(limit=limit):
        if suggestion.get("status") != "pending":
            continue
        result = test(suggestion)
        trials.append(
            SuggestionTrial(
                suggestion_id=str(suggestion.get("id")),
                accepted=result.accepted,
                reason=result.reason,
                validation=result.to_dict(),
            )
        )
    return trials


def search_entire(query: str, *, repo_path: str | Path = ".") -> str:
    """Search captured Entire history when the CLI and local session data are available."""
    if not shutil.which("entire"):
        raise ConfigurationError("Entire CLI is not installed.")
    process = subprocess.run(
        ["entire", "search", query],
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode:
        raise ExternalToolError(f"Entire search failed: {process.stderr.strip()}")
    return process.stdout


def entire_status(*, repo_path: str | Path = ".") -> str:
    if not shutil.which("entire"):
        return "Entire CLI is not installed."
    process = subprocess.run(
        ["entire", "status"], cwd=repo_path, text=True, capture_output=True, check=False
    )
    return process.stdout.strip() or process.stderr.strip()


def write_business_inputs(
    path: str | Path,
    *,
    baseline_success_rate: float | None,
    healed_success_rate: float | None,
    baseline_cost_usd: float | None,
    healed_cost_usd: float | None,
    evaluated_runs: int,
) -> dict[str, Any]:
    """Write only measured inputs; unknown values remain the string 'TBD'."""
    measured: dict[str, Any] = {
        "baseline_success_rate": _measured(baseline_success_rate),
        "healed_success_rate": _measured(healed_success_rate),
        "baseline_cost_usd": _measured(baseline_cost_usd),
        "healed_cost_usd": _measured(healed_cost_usd),
        "evaluated_runs": evaluated_runs,
        "pricing": "TBD",
        "revenue": "TBD",
        "runway": "TBD",
        "scenario_note": "Complete pricing, revenue, runway, and scenarios in cfo.ai.",
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(measured, indent=2) + "\n")
    return measured


def _measured(value: float | None) -> float | str:
    return "TBD" if value is None else value
