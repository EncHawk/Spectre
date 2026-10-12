from healer.models import Span, Trace
from healer.store import LocalTraceStore


def test_generated_ids_survive_redaction_and_keep_parent_link(tmp_path):
    root = "1" * 32
    child = "2" * 32
    trace_id = "3" * 32
    trace = Trace(
        trace_id,
        "agent",
        spans=[
            Span(root, trace_id, "agent", kind="AGENT", input="card 4111111111111111"),
            Span(child, trace_id, "tool", kind="TOOL", parent_id=root),
        ],
    )
    store = LocalTraceStore(tmp_path / "runs.jsonl")
    store.append(trace)
    loaded = store.list(since="1h")[0]
    assert loaded.id == trace_id
    assert loaded.spans[0].id == root
    assert loaded.spans[1].parent_id == root
    assert "4111111111111111" not in str(loaded.spans[0].input)
