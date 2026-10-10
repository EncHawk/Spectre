from __future__ import annotations

import json
from typing import Any

from .errors import HealerError
from .providers.bedrock import BedrockProvider

# Backwards-compatible name from the first SDK release.
BedrockModel = BedrockProvider


def extract_json(text: str) -> dict[str, Any]:
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
