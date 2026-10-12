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


def test_probe_checks_trace_read_scope_and_all_history_omits_from_filter():
    calls = []

    def transport(method, url, headers):
        calls.append((url, headers))
        if url.endswith("/project"):
            return response(200, {"data": {"id": "project"}})
        return response(200, {"data": {"traces": [], "page": {"nextCursor": None}}})

    client = NeatlogsClient("secret", "project", transport=transport)
    client.probe_reads()
    client.list_traces(since="all")
    assert calls[0][1]["Authorization"] == "Bearer secret"
    assert all(call[1]["x-project-id"] == "project" for call in calls)
    assert "from=" not in calls[-1][0]


def test_all_history_follows_every_cursor_before_loading_spans():
    calls = []

    def transport(method, url, headers):
        calls.append(url)
        if "/spans" in url:
            return response(200, {"data": {"spans": [], "page": {"nextCursor": None}}})
        if "cursor=next" in url:
            return response(200, {"data": {"traces": [{"traceId": "two"}], "page": {"nextCursor": None}}})
        return response(200, {"data": {"traces": [{"traceId": "one"}], "page": {"nextCursor": "next"}}})

    traces = NeatlogsClient("secret", "project", transport=transport).list_traces(
        since="all", limit=None, max_pages=None
    )
    assert [trace.id for trace in traces] == ["one", "two"]
    assert "cursor=next" in calls[1]
    assert "/spans" in calls[2]


def test_project_discovery_has_no_project_header_and_workflows_use_project_header():
    calls = []

    def transport(method, url, headers):
        calls.append((url, headers))
        if "/projects" in url:
            return response(200, {"data": {"projects": [{"id": "p1", "name": "Orders", "role": "project_viewer"}],
                                            "page": {"nextCursor": None}}})
        return response(200, {"data": {"traces": [
            {"traceId": "a", "workflowName": "support"},
            {"traceId": "b", "workflowName": "research"},
            {"traceId": "c", "workflowName": "support"}], "page": {"nextCursor": None}}})

    discovery = NeatlogsClient("token", None, transport=transport)
    assert discovery.list_projects() == [{"id": "p1", "name": "Orders", "role": "project_viewer"}]
    assert "x-project-id" not in calls[0][1]
    assert NeatlogsClient("token", "p1", transport=transport).list_workflows() == ["research", "support"]
    assert calls[1][1]["x-project-id"] == "p1"


def test_trace_sync_filters_workflow_and_from_timestamp():
    calls = []

    def transport(method, url, headers):
        calls.append(url)
        if "/spans" in url:
            return response(200, {"data": {"spans": [], "page": {"nextCursor": None}}})
        return response(200, {"data": {"traces": [{"traceId": "a"}], "page": {"nextCursor": None}}})

    client = NeatlogsClient("token", "p1", transport=transport)
    client.list_traces(since="all", limit=None, max_pages=None,
                       workflow_name="support agent", from_timestamp="2026-10-12T00:00:00+00:00")
    assert "workflowName=support+agent" in calls[0]
    assert "from=2026-10-12T00%3A00%3A00%2B00%3A00" in calls[0]
