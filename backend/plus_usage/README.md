# Competitor lead agent

Give this LangGraph agent a company website. It profiles the site, uses Parallel Entity Search to find candidate company leads, researches each candidate with Parallel Task API, and writes a JSON competitor report. Spectre Healer traces the graph run and its tools; Neatlogs receives traces when `NEATLOGS_API_KEY` is configured. OpenAI candidate ranking is optional through the SDK's provider adapter.

## Goals

1. Find direct competitor company leads, not individual contact details.
2. Explain each company's product, ideal customer, and problem solved.
3. Report dated growth numbers only when Parallel returns source URLs. Missing numbers stay missing.
4. Keep the research and model steps visible to Healer for later evaluation and repair.

## Run

From the repository root, with Python 3.12:

```bash
cd backend
pip install -r plus_usage/requirements.txt
cp plus_usage/.env.example plus_usage/.env
# Fill in PARALLEL_API_KEY. Add the optional keys only for the features you want to test.
set -a; source plus_usage/.env; set +a
healer --json status
python -m plus_usage.agent https://your-company.com --limit 5 --output competitor-leads.json
python -m plus_usage.agent https://your-company.com --limit 5 --openai-model gpt-5-mini
```

The agent makes one Parallel Task call for the input site, one Entity Search call, and up to twice `--limit` Task calls while checking candidate relevance. Task runs can take minutes and incur API charges. The JSON includes Parallel run IDs and source URLs for the research fields. A growth metric without a source URL is omitted. Entity Search is a recall-oriented lead pool, so a candidate is included only after its Task research marks it a competitor; the report can contain fewer leads than requested.

The graph is `profile → discover → rank → enrich → report`. `rank` uses the Healer OpenAI adapter only when `--openai-model` is passed. No outreach or cold calls are sent by this agent.

To inspect the agent's traces and SDK findings after a run:

```bash
healer --json scan --since 24h --tag competitor-research
healer --json doctor --repo .
python -m plus_usage.checks
```

The `healer` commands use Neatlogs reads when separately configured for Public API access, or the local `.healer/runs.jsonl` fallback. `python -m plus_usage.checks` always scans the local trace so its agent-specific checks see the complete report. `healer --json status` shows whether ingest, reads, and model generation are actually available. A missing Neatlogs key does not prevent local mistake detection. The agent-specific check reports product, ICP, problem, competitor-fit, and growth claims that lack source URLs. The SDK's built-in checks also catch execution failures. These are review signals, not proof that a sourced claim is true. The test suite verifies both a missing-evidence finding and a `no_recovery` finding from a failed Parallel call. The agent only performs research; the SDK's repair actions remain separate operator steps.

Parallel API references: [Entity Search](https://docs.parallel.ai/findall-api/entity-search), [Task API](https://docs.parallel.ai/task-api/task-quickstart), [Research Basis](https://docs.parallel.ai/task-api/guides/access-research-basis).
