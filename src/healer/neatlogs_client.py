from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .errors import AuthenticationError, HealerError, PermissionDeniedError, RateLimitError
from .models import Span, Trace
from .timeutil import parse_since


@dataclass(slots=True)
class _Response:
    status: int
    headers: Any
    body: dict[str, Any]


Transport = Callable[[str, str, dict[str, str]], _Response]


class NeatlogsClient:
    """Minimal client for the documented Neatlogs Public API read surface."""

    def __init__(
        self,
        token: str,
        project_id: str,
        host: str = "https://app.neatlogs.com",
        *,
        transport: Transport | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self.project_id = project_id
        self.host = host.rstrip("/")
        self._transport = transport or self._urlopen
        self._max_retries = max_retries
        self._sleep = sleep

    @property
    def base_url(self) -> str:
        return f"{self.host}/api/v1/public"

    def probe(self) -> None:
        self._request("/project")

    def list_traces(
        self,
        *,
        since: str = "24h",
        tag: str | None = None,
        trace_id: str | None = None,
        limit: int = 100,
        max_pages: int = 20,
    ) -> list[Trace]:
        if trace_id:
            raw = self._request(f"/traces/{urllib.parse.quote(trace_id, safe='')}")
            item = raw.get("data", raw)
            trace = Trace.from_dict(item, source="neatlogs")
            self._hydrate_spans(trace)
            return [trace]
        cursor: str | None = None
        results: list[Trace] = []
        for _ in range(max_pages):
            query: dict[str, Any] = {
                "limit": min(limit, 50),
                "from": parse_since(since).isoformat(),
            }
            if cursor:
                query["cursor"] = cursor
            body = self._request("/traces?" + urllib.parse.urlencode(query))
            data = body.get("data") or {}
            items = data.get("traces") if isinstance(data, dict) else data
            for item in items or []:
                if isinstance(item, dict):
                    trace = Trace.from_dict(item, source="neatlogs")
                    if not tag or tag in trace.tags:
                        self._hydrate_spans(trace)
                        results.append(trace)
            page = data.get("page") if isinstance(data, dict) else None
            cursor = page.get("nextCursor") if isinstance(page, dict) else None
            if not cursor or len(results) >= limit:
                break
        return results[:limit]

    def _hydrate_spans(self, trace: Trace) -> None:
        if trace.spans:
            return
        cursor: str | None = None
        spans: list[Span] = []
        for _ in range(10):
            query = {"limit": 50}
            if cursor:
                query["cursor"] = cursor
            suffix = "?" + urllib.parse.urlencode(query)
            body = self._request(f"/traces/{urllib.parse.quote(trace.id, safe='')}/spans{suffix}")
            data = body.get("data") or {}
            items = data.get("spans") if isinstance(data, dict) else data
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                span = Span.from_dict(item, trace.id)
                self._hydrate_payload(span)
                spans.append(span)
            page = data.get("page") if isinstance(data, dict) else None
            cursor = page.get("nextCursor") if isinstance(page, dict) else None
            if not cursor:
                break
        trace.spans = spans

    def _hydrate_payload(self, span: Span) -> None:
        trace_id = urllib.parse.quote(span.trace_id, safe="")
        span_id = urllib.parse.quote(span.id, safe="")
        body = self._request(
            f"/traces/{trace_id}/spans/{span_id}/payload?fields=error%2Cinput%2Coutput"
        )
        data = body.get("data") or {}
        fields = data.get("fields") if isinstance(data, dict) else {}
        if not isinstance(fields, dict):
            return
        span.input = _payload_value(fields.get("input"))
        span.output = _payload_value(fields.get("output"))
        error = _payload_value(fields.get("error"))
        span.error = str(error) if error is not None else None

    def list_fix_suggestions(self, *, limit: int = 50, max_pages: int = 20) -> list[dict[str, Any]]:
        """Read Neatlogs detection suggestions; accepting them is intentionally out of scope."""
        cursor: str | None = None
        suggestions: list[dict[str, Any]] = []
        for _ in range(max_pages):
            query: dict[str, Any] = {"limit": min(limit, 50)}
            if cursor:
                query["cursor"] = cursor
            body = self._request("/detection-suggestions?" + urllib.parse.urlencode(query))
            data = body.get("data") or {}
            items = data.get("suggestions") if isinstance(data, dict) else []
            suggestions.extend(item for item in items or [] if isinstance(item, dict))
            page = data.get("page") if isinstance(data, dict) else None
            cursor = page.get("nextCursor") if isinstance(page, dict) else None
            if not cursor or len(suggestions) >= limit:
                break
        return suggestions[:limit]

    def _request(self, path: str) -> dict[str, Any]:
        url = self.base_url + path
        headers = {
            "Authorization": f"Bearer {self._token}",
            "x-project-id": self.project_id,
            "Accept": "application/json",
            "User-Agent": "spectre-healer/0.1",
        }
        for attempt in range(self._max_retries + 1):
            try:
                response = self._transport("GET", url, headers)
            except urllib.error.HTTPError as exc:
                body = _decode_error(exc)
                response = _Response(exc.code, exc.headers, body)
            except urllib.error.URLError as exc:
                raise HealerError(f"Could not reach Neatlogs Public API: {exc.reason}") from exc
            if response.status == 401:
                raise AuthenticationError(
                    "Neatlogs rejected the read token (invalid, expired, revoked, or wrong host)."
                )
            if response.status == 403:
                raise PermissionDeniedError(
                    "Neatlogs read access requires a project-bound service-account token with "
                    "context:read and observability:read. Ingest API keys cannot read traces."
                )
            if response.status == 429:
                if attempt >= self._max_retries:
                    raise RateLimitError("Neatlogs rate limit persisted after bounded retries.")
                retry_after = _retry_after(response.headers, attempt)
                self._sleep(retry_after)
                continue
            if response.status >= 400:
                code = response.body.get("code", "unknown")
                request_id = response.body.get("requestId", "unknown")
                raise HealerError(
                    f"Neatlogs request failed ({response.status}, code={code}, requestId={request_id})."
                )
            return response.body
        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _urlopen(method: str, url: str, headers: dict[str, str]) -> _Response:
        request = urllib.request.Request(url, method=method, headers=headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
            return _Response(response.status, response.headers, body)


def _retry_after(headers: Any, attempt: int) -> float:
    try:
        return min(float(headers.get("Retry-After", "")), 30.0)
    except (TypeError, ValueError):
        return min((2**attempt) + random.random(), 30.0)


def _decode_error(exc: urllib.error.HTTPError) -> dict[str, Any]:
    try:
        return json.loads(exc.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _payload_value(field: Any) -> Any:
    if not isinstance(field, dict) or not field.get("available"):
        return None
    value = field.get("value")
    mime = str(field.get("mimeType") or "")
    if isinstance(value, str) and "json" in mime:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value
