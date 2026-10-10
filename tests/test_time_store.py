from datetime import UTC, datetime

import pytest

from healer.errors import ConfigurationError
from healer.models import Trace
from healer.store import LocalTraceStore
from healer.timeutil import parse_since


def test_parse_duration_and_iso():
    assert parse_since("24h") < datetime.now(UTC)
    assert parse_since("2026-01-01T00:00:00Z").year == 2026


def test_parse_invalid_time():
    with pytest.raises(ConfigurationError):
        parse_since("yesterday-ish")


def test_store_round_trip_and_tag_filter(tmp_path):
    store = LocalTraceStore(tmp_path / "runs.jsonl")
    store.append(Trace(id="one", name="a", tags=["wanted"]))
    store.append(Trace(id="two", name="b", tags=["other"]))
    traces = store.list("1h", tags=["wanted"])
    assert [trace.id for trace in traces] == ["one"]


def test_store_skips_corrupt_lines(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text("not-json\n")
    assert LocalTraceStore(path).list("1h") == []
