from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any, ClassVar

from ..errors import ConfigurationError
from ..privacy import Redactor


@dataclass(slots=True)
class Generation:
    """Provider-neutral text generation result."""

    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None


class Provider(ABC):
    """Small common surface over the official provider SDKs."""

    name: ClassVar[str]
    package: ClassVar[str]
    module: ClassVar[str]
    extra: ClassVar[str]
    key_envs: ClassVar[tuple[str, ...]] = ()
    model_env: ClassVar[str]

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        self.model = model or os.getenv(self.model_env) or os.getenv("HEALER_MODEL")
        self._api_key = api_key or next(
            (value for key in self.key_envs if (value := os.getenv(key))), None
        )
        self._client = client
        self._redactor = Redactor()
        if not self.model:
            raise ConfigurationError(
                f"Set {self.model_env} or HEALER_MODEL, or pass model= for {self.name}."
            )

    @property
    def family(self) -> str:
        return self.model.split(".", 1)[0].split("-", 1)[0]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r})"

    def validate_setup(self) -> None:
        """Validate local auth and SDK availability without making a network call."""
        if self._client is not None:
            return
        if self.key_envs:
            self._require_api_key()
        try:
            available = find_spec(self.module) is not None
        except ModuleNotFoundError:
            available = False
        if not available:
            raise self._missing_sdk(ImportError(self.module))

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = 0.1,
    ) -> Generation:
        """Generate text and record the provider call as a redacted LLM span."""
        safe_prompt = self._redactor.redact_text(prompt)
        safe_system = self._redactor.redact_text(system) if system else None
        from ..runtime import get_runtime

        invoke = get_runtime().instrument(
            self._generate,
            name=f"healer.{self.name}",
            kind="LLM",
            tags=("healer-provider", self.name),
        )
        return invoke(safe_prompt, safe_system, max_tokens, temperature)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = 0.1,
    ) -> str:
        return self.generate(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        ).text

    def _require_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        keys = " or ".join(self.key_envs)
        raise ConfigurationError(f"Set {keys}, or pass api_key= for {self.name}.")

    def _client_or_create(self) -> Any:
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _missing_sdk(self, exc: ImportError) -> ConfigurationError:
        return ConfigurationError(
            f"Install the '{self.extra}' extra to use {self.name}: "
            f"pip install 'spectre-healer[{self.extra}]'"
        )

    @abstractmethod
    def _create_client(self) -> Any: ...

    @abstractmethod
    def _generate(
        self,
        prompt: str,
        system: str | None,
        max_tokens: int,
        temperature: float | None,
    ) -> Generation: ...


def usage_value(usage: Any, *names: str) -> int | None:
    for name in names:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None
