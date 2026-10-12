from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterable
from pathlib import Path

from .models import Trace
from .privacy import Redactor
from .timeutil import parse_since, parse_timestamp


class LocalTraceStore:
    """Append-only redacted JSONL fallback; deliberately has no analytics or tracking."""

    def __init__(self, path: str | Path, redactor: Redactor | None = None) -> None:
        self.path = Path(path)
        self.redactor = redactor or Redactor()
        self._lock = threading.Lock()

    def append(self, trace: Trace) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.redactor.redact(trace.to_dict())
        # Trace/span IDs are generated opaque UUID hex values. Redacting the
        # whole structure can mistake a run of hex digits for a payment card,
        # destroying parent links and exact trace lookup.
        opaque_id = re.compile(r"[a-f0-9]{32}\Z")
        if opaque_id.fullmatch(trace.id):
            payload["id"] = trace.id
        for stored, original in zip(payload["spans"], trace.spans, strict=True):
            for key in ("id", "trace_id", "parent_id"):
                identifier = getattr(original, key)
                if isinstance(identifier, str) and opaque_id.fullmatch(identifier):
                    stored[key] = identifier
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def list(self, since: str = "24h", tags: Iterable[str] | None = None) -> list[Trace]:
        if not self.path.exists():
            return []
        threshold = parse_since(since)
        required = set(tags or [])
        traces: list[Trace] = []
        with self.path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    raw = json.loads(line)
                    trace = Trace.from_dict(raw, source="local")
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if parse_timestamp(trace.started_at) < threshold:
                    continue
                if required and not required.issubset(set(trace.tags)):
                    continue
                traces.append(trace)
        return traces
