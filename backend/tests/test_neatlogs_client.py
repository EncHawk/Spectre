import pytest

from healer.errors import AuthenticationError, PermissionDeniedError, RateLimitError
from healer.neatlogs_client import NeatlogsClient, _Response


def response(status, body, headers=None):
    return _Response(status, headers or {}, body)


def test_lists_pages_and_hydrates_payloads():
    calls = []

    def transport(method, url, headers):
        calls.append(url)
        if "/payload" in url:
            return response(
                200,
                {
                    "data": {
                        "fields": {
                            "input": {
                                "available": True,
                                "value": '{"q":"x"}',
                                "mimeType": "application/json",
                            },
                            "output": {"available": True, "value": "ok", "mimeType": "text/plain"},
                            "error": {"available": False, "value": None, "mimeType": None},
                        }
                    }
                },
            )
        if "/spans" in url:
            return response(
                200,
                {
                    "data": {
                        "spans": [
                            {
                                "spanId": "s",
                                "traceId": "t",
                                "spanName": "search",
                                "spanType": "TOOL",
                                "status": "ok",
                            }
                        ],
                        "page": {"nextCursor": None},
                    }
                },
            )
        return response(
            200,
            {
                "data": {
                    "traces": [
                        {
                            "traceId": "t",
                            "traceName": "run",
                            "startedAt": "2026-01-01T00:00:00Z",
                            "tags": ["x"],
                            "totalCostUsd": 0.25,
                        }
                    ],
                    "page": {"nextCursor": None},
                }
            },
        )

    client = NeatlogsClient("token", "project", transport=transport)
    traces = client.list_traces(since="24h", tag="x")
    assert traces[0].spans[0].input == {"q": "x"}
    assert traces[0].cost_usd == 0.25
    assert any("from=" in url for url in calls)


@pytest.mark.parametrize(
    ("status", "error"), [(401, AuthenticationError), (403, PermissionDeniedError)]
)
def test_auth_errors(status, error):
    client = NeatlogsClient("t", "p", transport=lambda *_: response(status, {}))
    with pytest.raises(error):
        client.probe()


def test_rate_limit_retries_then_raises():
    sleeps = []
    client = NeatlogsClient(
        "t",
        "p",
        transport=lambda *_: response(429, {}, {"Retry-After": "0"}),
        max_retries=1,
        sleep=sleeps.append,
    )
    with pytest.raises(RateLimitError):
        client.probe()
    assert sleeps == [0.0]


def test_fix_suggestions_only_read():
    client = NeatlogsClient(
        "t",
        "p",
        transport=lambda *_: response(
            200, {"data": {"suggestions": [{"id": "one"}], "page": {"nextCursor": None}}}
        ),
    )
    assert client.list_fix_suggestions() == [{"id": "one"}]
