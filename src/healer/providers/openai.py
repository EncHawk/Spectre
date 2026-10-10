from __future__ import annotations

from typing import Any

from ..errors import ProviderError
from .base import Generation, Provider, usage_value


class OpenAIProvider(Provider):
    name = "openai"
    package = "openai"
    module = "openai"
    extra = "openai"
    key_envs = ("OPENAI_API_KEY",)
    model_env = "OPENAI_MODEL"

    def _create_client(self) -> Any:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise self._missing_sdk(exc) from exc
        return OpenAI(api_key=self._require_api_key())

    def _generate(self, prompt, system, max_tokens, temperature) -> Generation:
        options: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max_tokens,
        }
        if system:
            options["instructions"] = system
        if temperature is not None:
            options["temperature"] = temperature
        try:
            response = self._client_or_create().responses.create(**options)
        except Exception as exc:
            raise ProviderError(f"OpenAI generation failed ({type(exc).__name__}).") from exc
        usage = getattr(response, "usage", None)
        input_tokens = usage_value(usage, "input_tokens")
        output_tokens = usage_value(usage, "output_tokens")
        return Generation(
            text=str(response.output_text),
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=usage_value(usage, "total_tokens")
            or ((input_tokens or 0) + (output_tokens or 0) or None),
            request_id=getattr(response, "_request_id", None),
        )
