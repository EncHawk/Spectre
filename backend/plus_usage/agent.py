"""LangGraph competitor research using Parallel for web evidence and Healer for traces."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlparse

import healer


class ResearchState(TypedDict, total=False):
    website: str
    limit: int
    profile: dict[str, Any]
    candidates: list[dict[str, str]]
    leads: list[dict[str, Any]]
    report: dict[str, Any]


def normalize_website(value: str) -> str:
    url = value.strip()
    if not url:
        raise ValueError("A website is required.")
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Website must be a public http(s) URL.")
    if parsed.username or parsed.password:
        raise ValueError("Website must not contain credentials.")
    return f"{parsed.scheme}://{parsed.hostname.lower()}"


def _entity_website(entity: Any) -> str:
    """Prefer a company's stated site over an Entity Search directory profile URL."""
    description = str(getattr(entity, "description", "") or "")
    match = re.search(r"\bWebsite Url:\s*([^\s|;,]+)", description, re.IGNORECASE)
    raw_url = match.group(1).rstrip(".)") if match else str(entity.url)
    url = normalize_website(raw_url)
    host = urlparse(url).hostname or ""
    if host in {"linkedin.com", "www.linkedin.com", "platform.tracxn.com"}:
        raise ValueError("Entity Search returned a directory page, not a company website.")
    return url


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


PROFILE_SCHEMA = _object(
    {
        "name": {"type": "string"},
        "what_they_do": {"type": "string"},
        "product": {"type": "string"},
        "icp": {"type": "string", "description": "Likely ideal customer profile"},
        "problem_solved": {"type": "string"},
    }
)

LEAD_SCHEMA = _object(
    {
        "name": {"type": "string"},
        "website": {"type": "string"},
        "is_competitor": {"type": "boolean"},
        "why_competitor": {"type": "string"},
        "what_they_do": {"type": "string"},
        "product": {"type": "string"},
        "icp": {"type": "string"},
        "problem_solved": {"type": "string"},
        "growth_metrics": {
            "type": "array",
            "description": "Only public, dated, quantitative growth facts; empty when none are verified",
            "items": _object(
                {
                    "metric": {"type": "string"},
                    "value": {"type": "string", "description": "Exact number and unit"},
                    "period": {"type": "string", "description": "Date or reporting period"},
                    "context": {"type": "string", "description": "What this number measures"},
                }
            ),
        },
        "growth_unknowns": {"type": "array", "items": {"type": "string"}},
    }
)


def _plain(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _task_content(result: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output = _plain(result.output)
    if not isinstance(output, dict) or not isinstance(output.get("content"), dict):
        raise TypeError("Parallel returned no structured task content.")
    basis = output.get("basis") or []
    return output["content"], [_plain(item) for item in basis]


def _evidence(basis: list[dict[str, Any]], field: str) -> dict[str, Any]:
    matches = [
        item
        for item in basis
        if item.get("field") == field or str(item.get("field", "")).startswith(field + ".")
    ]
    urls = list(
        dict.fromkeys(
            citation["url"]
            for item in matches
            for citation in item.get("citations", [])
            if isinstance(citation, dict) and citation.get("url")
        )
    )
    return {"sources": urls, "confidence": matches[0].get("confidence") if matches else None}


def _validated_lead(
    content: dict[str, Any], basis: list[dict[str, Any]], run_id: str
) -> dict[str, Any]:
    lead = {
        key: content.get(key)
        for key in (
            "name",
            "website",
            "is_competitor",
            "why_competitor",
            "what_they_do",
            "product",
            "icp",
            "problem_solved",
            "growth_unknowns",
        )
    }
    lead["parallel_run_id"] = run_id
    lead["evidence"] = {
        field: _evidence(basis, field)
        for field in ("why_competitor", "what_they_do", "product", "icp", "problem_solved")
    }
    lead["growth_metrics"] = []
    for index, metric in enumerate(content.get("growth_metrics") or []):
        evidence = _evidence(basis, f"growth_metrics.{index}")
        if (
            isinstance(metric, dict)
            and evidence["sources"]
            and re.search(r"\d", str(metric.get("value", "")))
            and re.search(r"\b(?:19|20)\d{2}\b", str(metric.get("period", "")))
        ):
            lead["growth_metrics"].append({**metric, **evidence})
    return lead


def build_agent(parallel_client: Any, *, openai_model: str | None = None):
    """Compile a graph. Client/model are captured, so API keys never enter span inputs."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("Install plus_usage/requirements.txt to use this agent.") from exc

    model = healer.provider("openai", model=openai_model) if openai_model else None

    @healer.tool
    def profile_site(website: str) -> dict[str, Any]:
        run = parallel_client.task_run.create(
            input=(
                f"Research the company at {website}. Use its actual website as the identity anchor. "
                "Describe its product, customer, and problem. Do not infer unsupported facts."
            ),
            task_spec={"output_schema": {"type": "json", "json_schema": PROFILE_SCHEMA}},
            processor="core",
        )
        content, basis = _task_content(
            parallel_client.task_run.result(run.run_id, api_timeout=1800)
        )
        return {"content": content, "basis": basis, "run_id": run.run_id}

    @healer.tool
    def discover_competitors(
        website: str, profile: dict[str, Any], pool_size: int
    ) -> list[dict[str, str]]:
        details = profile["content"]
        objective = (
            f"Companies directly competing with {details['name']} ({website}): "
            f"they sell a similar product ({details['product']}) to {details['icp']} "
            f"to solve {details['problem_solved']}. Include their company websites."
        )
        response = parallel_client.beta.findall.entity_search(
            entity_type="companies", objective=objective, match_limit=pool_size
        )
        own_host = (urlparse(website).hostname or "").removeprefix("www.")
        seen: set[str] = set()
        candidates = []
        for entity in response.entities:
            try:
                url = _entity_website(entity)
            except ValueError:
                continue
            host = (urlparse(url).hostname or "").removeprefix("www.")
            if host in seen or host == own_host:
                continue
            seen.add(host)
            candidates.append(
                {"name": entity.name, "website": url, "description": str(entity.description)[:400]}
            )
        return candidates[: max(20, pool_size // 5)]

    @healer.tool
    def rank_candidates(
        profile: dict[str, Any], candidates: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        if model is None or not candidates:
            return candidates
        answer = model.complete(
            "Rank the company websites by direct competitive overlap with the subject. "
            "Return only a JSON array of website strings from the candidates, no new websites.\n"
            + json.dumps({"subject": profile["content"], "candidates": candidates}),
            max_tokens=700,
            temperature=None,
        )
        try:
            ranking = json.loads(answer)
        except json.JSONDecodeError:
            return candidates
        if not isinstance(ranking, list):
            return candidates
        by_website = {item["website"]: item for item in candidates}
        ordered = []
        for url in ranking:
            if isinstance(url, str) and url in by_website and by_website[url] not in ordered:
                ordered.append(by_website[url])
        ordered.extend(item for item in candidates if item not in ordered)
        return ordered

    @healer.tool
    def research_competitor(subject: dict[str, Any], candidate: dict[str, str]) -> dict[str, Any]:
        run = parallel_client.task_run.create(
            input=(
                f"Research {candidate['name']} at {candidate['website']} as a possible competitor "
                f"to {subject['name']}, whose product is {subject['product']} for {subject['icp']}. "
                "Check whether the companies actually compete. Explain what this candidate builds, "
                "who buys it, and the problem it solves. Find dated, public growth numbers such as "
                "revenue growth, customer count, users, funding, or headcount, but distinguish funding "
                "from business growth. Never invent a number; use an empty growth_metrics list if needed."
            ),
            task_spec={"output_schema": {"type": "json", "json_schema": LEAD_SCHEMA}},
            processor="core",
        )
        content, basis = _task_content(
            parallel_client.task_run.result(run.run_id, api_timeout=1800)
        )
        return _validated_lead(content, basis, run.run_id)

    def profile_node(state: ResearchState) -> ResearchState:
        return {"profile": profile_site(state["website"])}

    def discover_node(state: ResearchState) -> ResearchState:
        pool_size = max(100, state["limit"] * 5)
        return {"candidates": discover_competitors(state["website"], state["profile"], pool_size)}

    def rank_node(state: ResearchState) -> ResearchState:
        return {"candidates": rank_candidates(state["profile"], state["candidates"])}

    def enrich_node(state: ResearchState) -> ResearchState:
        leads = []
        for candidate in state["candidates"][: state["limit"] * 2]:
            lead = research_competitor(state["profile"]["content"], candidate)
            if lead["is_competitor"] and lead["evidence"]["why_competitor"]["sources"]:
                leads.append(lead)
            if len(leads) >= state["limit"]:
                break
        return {"leads": leads}

    def report_node(state: ResearchState) -> ResearchState:
        profile = state["profile"]
        return {
            "report": {
                "goal": "Find and evidence direct competitor leads for the supplied website",
                "website": state["website"],
                "subject": profile["content"],
                "subject_evidence": {
                    field: _evidence(profile["basis"], field)
                    for field in ("name", "what_they_do", "product", "icp", "problem_solved")
                },
                "subject_parallel_run_id": profile["run_id"],
                "leads": state["leads"],
                "candidates_found": len(state["candidates"]),
            }
        }

    graph = StateGraph(ResearchState)
    graph.add_node("profile", profile_node)
    graph.add_node("discover", discover_node)
    graph.add_node("rank", rank_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "profile")
    graph.add_edge("profile", "discover")
    graph.add_edge("discover", "rank")
    graph.add_edge("rank", "enrich")
    graph.add_edge("enrich", "report")
    graph.add_edge("report", END)
    compiled = graph.compile()

    @healer.agent(tags=("competitor-research",))
    def run(website: str, limit: int = 5) -> dict[str, Any]:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        state = compiled.invoke({"website": normalize_website(website), "limit": limit})
        return state["report"]

    return run


def main() -> None:
    parser = argparse.ArgumentParser(description="Research competitor leads for a website")
    parser.add_argument("website", help="Website to analyze, such as https://example.com")
    parser.add_argument(
        "--limit", type=int, default=5, help="Researched competitors to return (1-20)"
    )
    parser.add_argument(
        "--openai-model", help="Optionally rank candidates through Healer's OpenAI adapter"
    )
    parser.add_argument("--output", type=Path, default=Path("competitor-leads.json"))
    args = parser.parse_args()
    if not os.getenv("PARALLEL_API_KEY"):
        parser.error("Set PARALLEL_API_KEY before running research.")
    if args.openai_model and not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY when using --openai-model.")
    try:
        from parallel import Parallel
    except ImportError as exc:
        parser.error(f"Install plus_usage/requirements.txt first: {exc}")
    healer.init(workflow_name="competitor-leads")
    report = build_agent(
        Parallel(api_key=os.environ["PARALLEL_API_KEY"]), openai_model=args.openai_model
    )(args.website, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(report['leads'])} researched competitor leads to {args.output}")


if __name__ == "__main__":
    main()
