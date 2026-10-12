from __future__ import annotations

from types import SimpleNamespace

import pytest

from healer.errors import ConfigurationError
from healer.providers import create_provider
from healer.runtime import init_runtime


class Call:
    def __init__(self, result):
        self.result = result
        self.options = None

    def create(self, **options):
        self.options = options
        return self.result


def test_openai_provider_uses_responses_api_and_redacts(tmp_path):
    call = Call(
        SimpleNamespace(
            output_text="done",
            usage=SimpleNamespace(input_tokens=4, output_tokens=2, total_tokens=6),
            _request_id="req-openai",
        )
    )
    client = SimpleNamespace(responses=call)
    runtime = init_runtime(local_log=tmp_path / "runs.jsonl")
    provider = create_provider("openai", model="gpt-test", client=client)

    result = provider.generate("api_key=sk-secret", system="Be exact")

    assert result.text == "done"
    assert result.total_tokens == 6
    assert "sk-secret" not in call.options["input"]
    assert runtime.store.list("1h")[0].spans[0].name == "healer.openai"


def test_groq_provider_uses_chat_completions(tmp_path):
    call = Call(
        SimpleNamespace(
            id="req-groq",
            choices=[SimpleNamespace(message=SimpleNamespace(content="fast"))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=1, total_tokens=4),
        )
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=call))
    init_runtime(local_log=tmp_path / "runs.jsonl")

    result = create_provider("groq", model="llama-test", client=client).generate("hello")

    assert result.text == "fast"
    assert call.options["messages"][-1] == {"role": "user", "content": "hello"}


def test_anthropic_provider_joins_text_blocks(tmp_path):
    call = Call(
        SimpleNamespace(
            id="req-anthropic",
            content=[
                SimpleNamespace(type="text", text="safe "),
                SimpleNamespace(type="tool_use", text="ignored"),
                SimpleNamespace(type="text", text="answer"),
            ],
            usage=SimpleNamespace(input_tokens=5, output_tokens=2),
        )
    )
    client = SimpleNamespace(messages=call)
    init_runtime(local_log=tmp_path / "runs.jsonl")

    result = create_provider("anthropic", model="claude-test", client=client).generate(
        "hello", system="Be safe"
    )

    assert result.text == "safe answer"
    assert result.total_tokens == 7
    assert call.options["system"] == "Be safe"


def test_google_provider_uses_generate_content(tmp_path):
    call = Call(
        SimpleNamespace(
            text="gemini",
            response_id="req-google",
            usage_metadata=SimpleNamespace(
                prompt_token_count=2,
                candidates_token_count=1,
                total_token_count=3,
            ),
        )
    )
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call.create))
    init_runtime(local_log=tmp_path / "runs.jsonl")

    result = create_provider("gemini", model="gemini-test", client=client).generate("hello")

    assert result.provider == "google"
    assert result.text == "gemini"
    assert call.options["config"]["max_output_tokens"] == 4096


def test_provider_requires_a_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("HEALER_MODEL", raising=False)
    with pytest.raises(ConfigurationError, match="OPENAI_MODEL"):
        create_provider("openai", client=object())


def test_unknown_provider_lists_choices():
    with pytest.raises(ConfigurationError, match="Unknown provider"):
        create_provider("made-up", model="x")
