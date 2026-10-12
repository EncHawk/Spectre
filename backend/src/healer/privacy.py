from __future__ import annotations

import re
from dataclasses import fields, is_dataclass
from typing import Any

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secret", re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^\s,'\"}]+")),
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/]+=*")),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("phone", re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")),
    ("card", re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")),
)
_SENSITIVE_KEYS = re.compile(r"(?i)(password|passwd|secret|token|api.?key|authorization|cookie)")
_ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


class Redactor:
    """Small, deterministic scrubber applied before persistence or model calls."""

    def redact_text(self, value: str) -> str:
        # Timestamps are structural trace data, not phone or card numbers.
        if _ISO_TIMESTAMP.fullmatch(value):
            return value
        result = value
        for label, pattern in _RULES:
            result = pattern.sub(f"[REDACTED:{label}]", result)
        return result

    def redact(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, bytes):
            return "[REDACTED:bytes]"
        if isinstance(value, dict):
            return {
                str(key): "[REDACTED:secret]"
                if _SENSITIVE_KEYS.search(str(key))
                else self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self.redact(item) for item in value]
        if is_dataclass(value) and not isinstance(value, type):
            return {f.name: self.redact(getattr(value, f.name)) for f in fields(value)}
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return self.redact_text(repr(value))
