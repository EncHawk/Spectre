import asyncio

import pytest

import healer
from healer.bedrock import BedrockModel
from healer.runtime import get_runtime, init_runtime, reset_runtime


def test_sync_instrumentation_records_nested_spans(tmp_path):
    healer.init(local_log=tmp_path / "runs.jsonl")
    runtime = get_runtime()

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
    healer.init(local_log=tmp_path / "runs.jsonl")
    runtime = get_runtime()

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


def test_agent_can_be_defined_before_init(tmp_path):
    reset_runtime()

    @healer.agent(tags=("early-definition",))
    def already_defined(value):
        return value + 1

    healer.init(local_log=tmp_path / "runs.jsonl")
    runtime = get_runtime()
    assert already_defined(2) == 3
    trace = runtime.store.list("1h")[0]
    assert trace.name == "already_defined"
    assert trace.tags == ["early-definition"]


def test_async_agent_can_be_defined_before_init(tmp_path):
    reset_runtime()

    @healer.agent
    async def already_defined():
        return "ready"

    healer.init(local_log=tmp_path / "runs.jsonl")
    runtime = get_runtime()
    assert asyncio.run(already_defined()) == "ready"
    assert runtime.store.list("1h")[0].spans[0].output == "ready"


def test_init_reports_missing_provider_auth_without_exposing_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    capability = healer.init(
        local_log=tmp_path / "runs.jsonl",
        provider="openai",
        model="gpt-test",
    )
    assert not capability.model_generation
    assert capability.model_provider is None
    assert "OPENAI_API_KEY" in capability.model_detail
