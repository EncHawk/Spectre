from __future__ import annotations

from typing import Any

from ..errors import ProviderError
from .base import Generation, Provider, usage_value


class GoogleProvider(Provider):
    name = "google"
    package = "google-genai"
    module = "google.genai"
    extra = "google"
    key_envs = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
    model_env = "GOOGLE_MODEL"

    def _create_client(self) -> Any:
        try:
            from google import genai  # type: ignore[import-not-found]
        except ImportError as exc:
            raise self._missing_sdk(exc) from exc
        return genai.Client(api_key=self._require_api_key())

    def _generate(self, prompt, system, max_tokens, temperature) -> Generation:
        config: dict[str, Any] = {"max_output_tokens": max_tokens}
        if system:
            config["system_instruction"] = system
        if temperature is not None:
            config["temperature"] = temperature
        try:
            response = self._client_or_create().models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise ProviderError(f"Google generation failed ({type(exc).__name__}).") from exc
        usage = getattr(response, "usage_metadata", None)
        return Generation(
            text=str(response.text or ""),
            provider=self.name,
            model=self.model,
            input_tokens=usage_value(usage, "prompt_token_count"),
            output_tokens=usage_value(usage, "candidates_token_count"),
            total_tokens=usage_value(usage, "total_token_count"),
            request_id=getattr(response, "response_id", None),
        )
