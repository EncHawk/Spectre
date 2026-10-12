from healer.models import Span, Trace
from healer.neatlogs_cache import NeatlogsTraceCache


def test_incremental_sync_keeps_prior_traces_and_isolates_users(tmp_path):
    class Client:
        def __init__(self):
            self.calls = []

        def list_traces(self, **kwargs):
            self.calls.append(kwargs)
            trace_id = "first" if len(self.calls) == 1 else "second"
            return [Trace(trace_id, "support", spans=[Span("span-" + trace_id, trace_id, "tool")])]

    cache = NeatlogsTraceCache(tmp_path / "neatlogs.sqlite")
    client = Client()
    assert [trace.id for trace in cache.sync("alice", "project", "support", client)] == ["first"]
    assert client.calls[0]["from_timestamp"] is None
    assert {trace.id for trace in cache.sync("alice", "project", "support", client)} == {"first", "second"}
    assert client.calls[1]["from_timestamp"] is not None
    assert client.calls[1]["workflow_name"] == "support"
    assert cache.list("bob", "project", "support") == []
    assert cache.list("alice", "other-project", "support") == []
