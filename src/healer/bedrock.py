from __future__ import annotations

import json
import os
from typing import Any

from .errors import ConfigurationError, HealerError
from .privacy import Redactor


class BedrockModel:
    """Thin adapter around the documented Bedrock Converse API."""

    def __init__(
        self, model_id: str | None = None, region: str | None = None, client: Any = None
    ) -> None:
        self.model_id = model_id or os.getenv("HEALER_BEDROCK_MODEL")
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self._client = client
        self._redactor = Redactor()

    @property
    def family(self) -> str:
        return (self.model_id or "unknown").split(".", 1)[0]

    def complete(self, prompt: str, *, max_tokens: int = 4096, temperature: float = 0.1) -> str:
        if not self.model_id:
            raise ConfigurationError(
                "Set HEALER_BEDROCK_MODEL before requesting an LLM-generated fix."
            )
        if self._client is None:
            try:
                import boto3  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ConfigurationError(
                    "Install the 'bedrock' extra to use Amazon Bedrock: pip install 'spectre-healer[bedrock]'"
                ) from exc
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        safe_prompt = self._redactor.redact_text(prompt)
        # Healer's own analysis is traced too, using the same redacted local/vendor path.
        from .runtime import get_runtime

        invoke = get_runtime().instrument(self._invoke, name="healer.bedrock", kind="LLM")
        return invoke(safe_prompt, max_tokens, temperature)

    def _invoke(self, safe_prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            response = self._client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": safe_prompt}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
            )
            blocks = response["output"]["message"]["content"]
            return "".join(str(block.get("text", "")) for block in blocks)
        except Exception as exc:
            raise HealerError(f"Bedrock model call failed: {type(exc).__name__}: {exc}") from exc


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
