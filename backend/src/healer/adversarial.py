from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ConfigurationError
from .models import RegressionCase


def variants(value: str) -> list[str]:
    compact = " ".join(value.split())
    return [
        compact,
        f"Please help me with this, but explain assumptions: {compact}",
        f"Context may be incomplete. {compact}",
        f"Quick answer needed — {compact}",
        compact.replace("?", " — be precise?"),
    ]


def variant_cases(cases: Iterable[RegressionCase]) -> list[RegressionCase]:
    transformed: list[RegressionCase] = []
    for case in cases:
        if not isinstance(case.input, str):
            continue
        for index, value in enumerate(variants(case.input)):
            transformed.append(
                RegressionCase(
                    id=f"{case.id}-v{index}",
                    finding_id=case.finding_id,
                    check=case.check,
                    input=value,
                    expected=case.expected,
                    trace_id=case.trace_id,
                )
            )
    return transformed


def attack(
    prompt: str,
    *,
    agent_model_family: str,
    attacker_model_family: str,
    complete: Callable[[str], str],
) -> list[str]:
    if agent_model_family.lower() == attacker_model_family.lower():
        raise ConfigurationError(
            "The attacker must use a different model family than the target agent."
        )
    request = (
        "Generate five concise adversarial user inputs that expose failures in this agent prompt. "
        "Return one input per line and no commentary. Do not include secrets.\n\n" + prompt
    )
    return [
        line.lstrip("- 0123456789.").strip()
        for line in complete(request).splitlines()
        if line.strip()
    ][:5]


@dataclass(slots=True)
class Fault:
    mode: str
    at_call: int = 1
    message: str = "injected failure"


def inject_fault(function: Callable[..., Any], fault: Fault) -> Callable[..., Any]:
    calls = 0

    @functools.wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == fault.at_call:
            if fault.mode == "error":
                raise RuntimeError(fault.message)
            if fault.mode == "empty":
                return None
            if fault.mode == "rate_limit":
                raise RuntimeError("429 rate limit (injected)")
            if fault.mode == "bad_data":
                return {"malformed": True, "injected": True}
            raise ConfigurationError(f"Unknown fault mode: {fault.mode}")
        return function(*args, **kwargs)

    return wrapped
