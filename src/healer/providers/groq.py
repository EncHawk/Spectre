from __future__ import annotations

from typing import Any

from ..errors import ProviderError
from .base import Generation, Provider, usage_value


class GroqProvider(Provider):
    name = "groq"
    package = "groq"
    module = "groq"
    extra = "groq"
    key_envs = ("GROQ_API_KEY",)
    model_env = "GROQ_MODEL"

    def _create_client(self) -> Any:
        try:
            from groq import Groq  # type: ignore[import-not-found]
        except ImportError as exc:
            raise self._missing_sdk(exc) from exc
        return Groq(api_key=self._require_api_key())

    def _generate(self, prompt, system, max_tokens, temperature) -> Generation:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        options: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if temperature is not None:
            options["temperature"] = temperature
        try:
            response = self._client_or_create().chat.completions.create(**options)
        except Exception as exc:
            raise ProviderError(f"Groq generation failed ({type(exc).__name__}).") from exc
        usage = getattr(response, "usage", None)
        return Generation(
            text=str(response.choices[0].message.content or ""),
            provider=self.name,
            model=self.model,
            input_tokens=usage_value(usage, "prompt_tokens"),
            output_tokens=usage_value(usage, "completion_tokens"),
            total_tokens=usage_value(usage, "total_tokens"),
            request_id=getattr(response, "id", None),
        )
