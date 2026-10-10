from __future__ import annotations

import os
import threading
from typing import Any

from ..errors import ConfigurationError
from .anthropic import AnthropicProvider
from .base import Provider
from .bedrock import BedrockProvider
from .google import GoogleProvider
from .groq import GroqProvider
from .openai import OpenAIProvider

_PROVIDERS: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "bedrock": BedrockProvider,
    "aws": BedrockProvider,
    "google": GoogleProvider,
    "gemini": GoogleProvider,
    "groq": GroqProvider,
    "openai": OpenAIProvider,
}
_default: Provider | None = None
_lock = threading.Lock()


def create_provider(
    name: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    client: Any = None,
    **options: Any,
) -> Provider:
    normalized = name.strip().lower()
    try:
        provider_type = _PROVIDERS[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted({item.name for item in _PROVIDERS.values()}))
        raise ConfigurationError(f"Unknown provider {name!r}. Choose one of: {choices}.") from exc
    return provider_type(model=model, api_key=api_key, client=client, **options)


def configure_default_provider(
    name: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    client: Any = None,
    **options: Any,
) -> Provider:
    global _default
    provider = create_provider(name, model=model, api_key=api_key, client=client, **options)
    with _lock:
        _default = provider
    return provider


def get_default_provider(*, required: bool = True) -> Provider | None:
    global _default
    if _default is None:
        name = os.getenv("HEALER_PROVIDER")
        if not name and os.getenv("HEALER_BEDROCK_MODEL"):
            name = "bedrock"
        if name:
            _default = create_provider(name)
    if _default is None and required:
        raise ConfigurationError(
            "Configure a model with healer.init(provider=..., model=...) or set "
            "HEALER_PROVIDER and the provider's model/key variables."
        )
    return _default


def reset_default_provider() -> None:
    global _default
    with _lock:
        _default = None
