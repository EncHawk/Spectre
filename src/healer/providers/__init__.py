"""Official-SDK adapters for the model providers supported by Spectre Healer."""

from .anthropic import AnthropicProvider
from .base import Generation, Provider
from .bedrock import BedrockProvider
from .google import GoogleProvider
from .groq import GroqProvider
from .openai import OpenAIProvider
from .registry import (
    configure_default_provider,
    create_provider,
    get_default_provider,
    reset_default_provider,
)

__all__ = [
    "AnthropicProvider",
    "BedrockProvider",
    "Generation",
    "GoogleProvider",
    "GroqProvider",
    "OpenAIProvider",
    "Provider",
    "configure_default_provider",
    "create_provider",
    "get_default_provider",
    "reset_default_provider",
]
