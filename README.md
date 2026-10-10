# Spectre Healer

Spectre Healer is a Python SDK that turns agent traces into a guarded repair loop:

`agent → trace → checks → regression cases → root cause → patch → visible + sealed tests → PR`

It works with any Python agent. It does not import or depend on the example agent, and every mutating operation is opt-in.

## Quickstart

```python
import healer

healer.init()                         # credentials come from the environment
findings = healer.scan(since="24h")  # Neatlogs when readable, local log otherwise
for finding in findings:
    print(finding.reason, finding.trace_url)

cases = healer.findings_to_cases(findings)
causes = healer.group_causes(findings)
```

Instrument any agent and its tools:

```python
import healer

healer.init(workflow_name="support-agent")

@healer.tool
def lookup_order(order_id: str):
    return {"status": "shipped"}

@healer.agent(tags=("production",))
def support_agent(order_id: str):
    return lookup_order(order_id)
```

Both sync and async functions are supported. Inputs, outputs, and errors are redacted before the local fallback log is written.

## Install and run

Python 3.12 is the supported hackathon runtime.

```bash
make setup
cp .env.example .env  # load it with your preferred secret manager; do not commit it
make test
make demo
```

The demo is deterministic and needs no live credentials. It traces a deliberately flawed research agent, finds a repeated tool call, groups the cause, generates a constrained patch, tests it against visible and sealed cases, and writes reports beneath `evidence/demo/`. Unknown costs and business values remain `TBD`.

## Credentials and capability detection

Neatlogs documents two distinct credential paths:

- `NEATLOGS_API_KEY` is an SDK ingest credential used to send traces.
- `NEATLOGS_TOKEN` is a project-bound service-account token used to read the Public API. Set `NEATLOGS_PROJECT_ID` with it. Trace reads require `context:read` and `observability:read`.

An ingest credential does not authorize Public API reads. `healer.init()` reports the exact capabilities it established and falls back to `.healer/runs.jsonl` when reads are unavailable. For an EU deployment, set `NEATLOGS_HOST=https://eu.app.neatlogs.com` and `NEATLOGS_INGEST_ENDPOINT=https://eu.ingest.neatlogs.com`.

```bash
healer --json status
healer --json scan --since 24h --tag production
healer --json report --output evidence/healer-report.json
```

The client follows opaque pagination cursors, respects `Retry-After`, bounds retries, and turns `401`, `403`, and persistent `429` responses into plain SDK errors.

## What the scanner checks

- identical repeated tool calls;
- ignored errors and runs with no recovery;
- repeating multi-step loops;
- cost above three times a measured corpus median (at least five samples);
- empty answers;
- source-sensitive claims without evidence;
- time-sensitive answers made without a lookup.

Checks are deterministic and evidence-backed. They do not use an LLM to invent a diagnosis.

## The repair boundary

`healer.propose_fix(...)` sends only redacted findings and cause groups to Amazon Bedrock's Converse API (or a caller-supplied completion function). It accepts only JSON containing a unified diff, rejects path traversal and files outside `allowed_files`, and writes the proposal under `.healer/proposals/` without touching source files.

Applying is a separate explicit call:

```python
proposal = healer.propose_fix(findings, repo_path=".", allowed_files=["agent.py"])
healer.apply_proposal(proposal, repo_path=".", branch="codex/heal-search-loop")
```

`apply_proposal` creates a branch and stages the patch only when called. `open_pull_request(...)` likewise refuses to open a PR unless `validate_candidate(...)` produced an accepted measured result.

## Breaking agents on purpose

The SDK includes deterministic prompt variants, a model-family guard for attacker generation, error/empty/rate-limit/bad-data fault injection, sealed test cases, and record/replay of tool outputs. Sealed inputs can be withheld from serialized output and are reported separately from visible cases.

## Sponsor adapters

- Neatlogs: SDK instrumentation, Public API traces/span payloads, detection suggestions (read-only), cursor pagination, bounded retries.
- Amazon Bedrock: Converse API for analysis/fix generation; all payloads are redacted first.
- Entire: existing CLI status and prior-session search. Entire is already enabled in this repository; approve the Codex hooks locally so commits receive checkpoints.
- cfo.ai: measured rates and costs are written to `business/inputs.json`; pricing, revenue, runway, and scenarios stay `TBD` for the user to complete in cfo.ai.

Crustdata is not in the runtime path yet because no core SDK feature needs external people/company data. GEPA and a second agent framework are intentionally deferred until the required loop is complete and proven with live credentials.

## Safety and privacy

- Read-only by default; no branch, patch, commit, remote write, or PR without an explicit API call.
- Secrets, bearer tokens, AWS keys, emails, phone numbers, and payment-card-like values are stripped before local persistence and model calls.
- No analytics or product tracking.
- Every score is calculated from executed cases. Missing measurements are `TBD`, never estimates presented as fact.

See [`backend/SPEC.md`](backend/SPEC.md) for the product contract and [`hackathon.md`](hackathon.md) for the dated build/evidence log.
