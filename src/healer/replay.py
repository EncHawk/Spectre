from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .privacy import Redactor


@dataclass(slots=True)
class ToolEvent:
    name: str
    arguments: Any
    output: Any = None
    error: str | None = None


class Recorder:
    def __init__(self) -> None:
        self.events: list[ToolEvent] = []
        self.redactor = Redactor()

    def wrap(self, name: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def recorded(*args: Any, **kwargs: Any) -> Any:
            arguments = self.redactor.redact({"args": args, "kwargs": kwargs})
            try:
                result = function(*args, **kwargs)
                self.events.append(ToolEvent(name, arguments, self.redactor.redact(result)))
                return result
            except Exception as exc:
                self.events.append(ToolEvent(name, arguments, error=f"{type(exc).__name__}: {exc}"))
                raise

        return recorded

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps([asdict(event) for event in self.events], indent=2) + "\n")


class Replayer:
    def __init__(self, events: list[ToolEvent], start_step: int = 0) -> None:
        self.events = events[start_step:]
        self.position = 0

    @classmethod
    def load(cls, path: str | Path, start_step: int = 0) -> Replayer:
        values = json.loads(Path(path).read_text())
        return cls([ToolEvent(**item) for item in values], start_step)

    def tool(self, name: str) -> Callable[..., Any]:
        def replayed(*args: Any, **kwargs: Any) -> Any:
            if self.position >= len(self.events):
                raise AssertionError(f"Replay exhausted before tool {name!r} was called.")
            event = self.events[self.position]
            self.position += 1
            if event.name != name:
                raise AssertionError(f"Replay expected {event.name!r}, got {name!r}.")
            if event.error:
                raise RuntimeError(event.error)
            return event.output

        return replayed
