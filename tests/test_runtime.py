import asyncio

import pytest

from healer.bedrock import BedrockModel
from healer.runtime import init_runtime


def test_sync_instrumentation_records_nested_spans(tmp_path):
    runtime = init_runtime(local_log=tmp_path / "runs.jsonl")

    @runtime.instrument
    def agent(value):
        return tool(value)

    @runtime.instrument
    def tool(value):
        return value + 1

    assert agent(1) == 2
    trace = runtime.store.list("1h")[0]
    assert len(trace.spans) == 2
    assert trace.spans[1].parent_id == trace.spans[0].id


def test_error_is_recorded_and_reraised(tmp_path):
    runtime = init_runtime(local_log=tmp_path / "runs.jsonl")

    @runtime.instrument
    def broken():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        broken()
    trace = runtime.store.list("1h")[0]
    assert trace.status == "error"
    assert "ValueError" in trace.spans[0].error


def test_async_instrumentation(tmp_path):
    runtime = init_runtime(local_log=tmp_path / "runs.jsonl")

    @runtime.instrument
    async def agent():
        return "ok"

    assert asyncio.run(agent()) == "ok"
    assert runtime.store.list("1h")[0].spans[0].output == "ok"


def test_local_capability_message(tmp_path, monkeypatch):
    monkeypatch.delenv("NEATLOGS_API_KEY", raising=False)
    monkeypatch.delenv("NEATLOGS_TOKEN", raising=False)
    runtime = init_runtime(local_log=tmp_path / "runs.jsonl")
    assert runtime.capability.local_fallback
    assert not runtime.capability.read_traces
    assert "NEATLOGS_TOKEN" in runtime.capability.read_detail


def test_healers_bedrock_call_is_traced(tmp_path):
    runtime = init_runtime(local_log=tmp_path / "runs.jsonl")

    class Client:
        def converse(self, **_):
            return {"output": {"message": {"content": [{"text": "fixed"}]}}}

    model = BedrockModel("amazon.nova-lite-v1:0", client=Client())
    assert model.complete("repair this") == "fixed"
    recorded = runtime.store.list("1h")
    assert recorded[0].spans[0].kind == "LLM"
    assert recorded[0].spans[0].name == "healer.bedrock"
