from __future__ import annotations

import os
from typing import Any

from ..errors import ConfigurationError, ProviderError
from .base import Generation, Provider, usage_value


class BedrockProvider(Provider):
    name = "bedrock"
    package = "boto3"
    module = "boto3"
    extra = "bedrock"
    model_env = "HEALER_BEDROCK_MODEL"

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        client: Any = None,
        region: str | None = None,
        model_id: str | None = None,
    ) -> None:
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        super().__init__(model or model_id, api_key=api_key, client=client)

    @property
    def model_id(self) -> str:
        return self.model

    def _create_client(self) -> Any:
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:
            raise self._missing_sdk(exc) from exc
        try:
            return boto3.client("bedrock-runtime", region_name=self.region)
        except Exception as exc:
            raise ConfigurationError(
                f"Amazon Bedrock client initialization failed ({type(exc).__name__})."
            ) from exc

    def _generate(self, prompt, system, max_tokens, temperature) -> Generation:
        options: dict[str, Any] = {
            "modelId": self.model,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if temperature is not None:
            options["inferenceConfig"]["temperature"] = temperature
        if system:
            options["system"] = [{"text": system}]
        try:
            response = self._client_or_create().converse(**options)
        except Exception as exc:
            raise ProviderError(f"Bedrock generation failed ({type(exc).__name__}).") from exc
        blocks = response["output"]["message"]["content"]
        usage = response.get("usage", {})
        return Generation(
            text="".join(str(block.get("text", "")) for block in blocks),
            provider=self.name,
            model=self.model,
            input_tokens=usage_value(usage, "inputTokens"),
            output_tokens=usage_value(usage, "outputTokens"),
            total_tokens=usage_value(usage, "totalTokens"),
            request_id=response.get("ResponseMetadata", {}).get("RequestId"),
        )
