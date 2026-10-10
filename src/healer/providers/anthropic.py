from __future__ import annotations

from typing import Any

from ..errors import ProviderError
from .base import Generation, Provider, usage_value


class AnthropicProvider(Provider):
    name = "anthropic"
    package = "anthropic"
    module = "anthropic"
    extra = "anthropic"
    key_envs = ("ANTHROPIC_API_KEY",)
    model_env = "ANTHROPIC_MODEL"

    def _create_client(self) -> Any:
        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise self._missing_sdk(exc) from exc
        return Anthropic(api_key=self._require_api_key())

    def _generate(self, prompt, system, max_tokens, temperature) -> Generation:
        options: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            options["system"] = system
        if temperature is not None:
            options["temperature"] = temperature
        try:
            response = self._client_or_create().messages.create(**options)
        except Exception as exc:
            raise ProviderError(f"Anthropic generation failed ({type(exc).__name__}).") from exc
        text = "".join(
            str(block.get("text", "") if isinstance(block, dict) else getattr(block, "text", ""))
            for block in response.content
            if (block.get("type") if isinstance(block, dict) else getattr(block, "type", None))
            == "text"
        )
        usage = getattr(response, "usage", None)
        input_tokens = usage_value(usage, "input_tokens")
        output_tokens = usage_value(usage, "output_tokens")
        return Generation(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens or 0) + (output_tokens or 0) or None,
            request_id=getattr(response, "id", None),
        )
