from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from .errors import ConfigurationError

_DURATION = re.compile(r"^(\d+)([mhdw])$")


def parse_since(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    match = _DURATION.fullmatch(value.strip().lower())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        delta = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }[unit]
        return datetime.now(UTC) - delta
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError as exc:
        raise ConfigurationError(
            f"Invalid time {value!r}; use a duration such as '24h' or an ISO-8601 timestamp."
        ) from exc


def parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
