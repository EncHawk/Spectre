"""Tiny intentionally flawed agent used by `make demo`."""

import healer


@healer.tool
def search(query: str) -> list[dict[str, str]]:
    return [{"title": "Demo result", "url": "https://example.invalid"}]


@healer.agent(tags=("demo",))
def research_agent(query: str) -> str:
    results = []
    for _ in range(3):  # duplicate calls are intentional so Healer has something to catch
        results.extend(search(query))
    return f"Found {len(results)} results."
