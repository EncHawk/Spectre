# Spectre Healer

Spectre Healer is a Python SDK and web workspace for investigating agent failures:

`agent → trace → checks → investigation → likely cause → suggested fix → replay plan`

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

@healer.tool
def lookup_order(order_id: str):
    return {"status": "shipped"}

@healer.agent(tags=("production",))
def support_agent(order_id: str):
    return lookup_order(order_id)

# Initialization can happen after definitions. Decorators bind to the active
# runtime on first use (and follow a later re-initialization).
capabilities = healer.init(
    workflow_name="support-agent",
    provider="openai",
    model="gpt-5-mini",
)

answer = support_agent("order-123")
```

Both sync and async functions are supported. Inputs, outputs, and errors are redacted before the local fallback log is written.

## Doctor and dashboard

Assign each chat an app and session ID, then run Doctor against a **local checkout** of its repository:

```python
with healer.session("support", "chat-42"):
    support_agent("order-123")

report = healer.doctor(repo_path="/path/to/support-repo", app_id="support", session_id="chat-42")
for row in report["rows"]:
    print(row["finding"]["reason"], row["suggestion"])
    print(row["copy_to_agent"])
```

`healer --json doctor --repo /path/to/support-repo --app-id support --session-id chat-42` prints the same JSON. Doctor reads recent traces, runs the existing deterministic checks, and indexes up to 500 Git-tracked Python files with the standard-library AST parser. It returns candidate function locations and GitHub permalinks when `origin` is a GitHub remote and `HEAD` exists. It stores no source bodies or AST dump. A name match is a navigation hint, not a proven root cause. Without a GitHub remote, the local file and line still appear.

The SDK writes `app_id` and `session_id` to its redacted local trace. For a filtered chat, Doctor prefers that record when present because Neatlogs' vendor trace may not carry these SDK-owned attributes. Unfiltered scans still use the configured Neatlogs read path when available. Cross-source trace ID correlation is not implemented yet.

For the HTTP service, mount the checkout read-only (for example `-v /path/to/support-repo:/repo:ro`) and set `HEALER_REPO_PATH=/repo`. Open `/app/` for all recent findings or `/app/<app-id>/<session-id>` for one chat. The page asks for `HEALER_SERVER_TOKEN` in the browser and calls authenticated `GET /v1/doctor`. Its table shows evidence, suggestions, candidate code, resolution history, PR links, and **Copy to Agent** text that can be pasted into Codex, Claude Code, or another agent. The token is held in browser session storage; use a dedicated trusted browser session for this operator dashboard.

Resolution updates are explicit: `healer.record_resolution(finding_id, status="investigating", note="...")` or authenticated `POST /v1/resolutions`. Events append to `.healer/resolutions.jsonl` locally, or `HEALER_RESOLUTION_LOG` in the service. A GitHub PR URL can be recorded after one exists. The Python dashboard does not create a PR: use `validate_candidate(...)` and then the existing explicit `open_pull_request(...)` call, which requires an accepted measured result. It does not connect to GitHub OAuth, clone a remote repository, or infer a fix from an AST match.

The separate Next.js control plane in `../frontend/` adds Google sign-in, GitHub OAuth repository snapshots, agent definitions, and a server-side bridge to Doctor. See [the integration handoff](INTEGRATION_HANDOFF.md) for environment variables, callback URLs, API routes, verification, and current limits.

### Project API keys

In the signed-in workspace, create a project, choose key scopes, and click **Create API key**. The request goes through a session-protected Next route to the Python service. Python generates an opaque `spk_...` key; Postgres stores only its prefix and SHA-256 hash. Copy the plaintext on that screen because subsequent key lists cannot recover it. Revocation takes effect on the next authenticated request. `GET /v1/whoami` accepts the project key and returns its project, app ID, prefix, and scopes.

The marketing page's **Sign in to workspace** button starts Google OAuth. A successful callback sets the existing HttpOnly session cookie and opens `/app`. Unauthenticated app requests return to the marketing page; signed-in users without an active key are sent to `/setup`. That page creates the key and shows a **Continue to app** link after issuance. The app checks active key state in Postgres, so revoked or expired keys return the user to setup on the next app request.

Apply `db/schema.sql` to Postgres before enabling this flow. Set `DATABASE_URL` and `HEALER_SERVER_TOKEN` on the Python service; set the same `HEALER_SERVER_TOKEN` plus `HEALER_API_URL` on the Next server. Google OAuth, `SPECTRE_ALLOWED_EMAIL`, and the existing SQLite session store remain on Next. See `.env.example` and `../frontend/.env.example` for the service-specific variables. The Python service holds `OPENAI_API_KEY` for model calls. A Spectre project key is separate from that provider key; set the issued value as `HEALER_API_KEY` in the customer's worker or SDK environment. The key flow itself makes no OpenAI request and does not measure or bill usage.

## Investigation and adversary

In the signed-in **Investigation** tab, select an agent and an observed finding, then choose **Investigate and suggest fix**. `POST /api/investigations` checks agent ownership and forwards to Python `POST /v1/investigations`. The response keeps trace evidence separate from a likely-cause hypothesis, suggested fix, and verification plan. If `OPENAI_API_KEY` is set on the Python service, OpenAI analyzes bounded source context from the pinned checkout. Otherwise the service returns a rule-based suggestion. This action does not change repository files.

Install `pip install -e '.[gepa]'` to run the optional GEPA prompt adversary. The caller supplies the target agent runner **and** a task-specific contract probe; this library does not launch arbitrary linked repositories. Set `GEPA_REFLECTION_MODEL` to a GEPA-supported model and configure that model's provider credentials, or pass `reflection_model` directly.

```python
from healer.adversary import ProbeResult, evolve_prompts

def probe(prompt: str) -> ProbeResult:
    answer, trace_id = run_my_agent(prompt)  # your bounded runner
    passed = my_task_contract(answer)         # True, False, or None if inconclusive
    return ProbeResult(passed, "Explain the contract result", trace_id)

report = evolve_prompts("Check order status", probe, stage="before", max_evaluations=12)
# After a measured failure: stage="after", failure_context="Observed timeout and false success"
```

GEPA receives feedback after each executed probe and searches for prompts that expose contract failures. The report lists attempts and trace IDs; an unrun optimizer candidate is never counted as a failure. The frontend trigger for user-provided agents is still to be designed.

## Model providers

Healer has a provider-neutral generation interface backed by each vendor's official Python SDK. Install only what you use, or install all adapters together:

```bash
pip install 'spectre-healer[openai]'
pip install 'spectre-healer[groq]'
pip install 'spectre-healer[anthropic]'
pip install 'spectre-healer[google]'
# or
pip install 'spectre-healer[providers]'
```

| Provider | `HEALER_PROVIDER` | API key | Model variable |
| --- | --- | --- | --- |
| OpenAI | `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` |
| Groq | `groq` | `GROQ_API_KEY` | `GROQ_MODEL` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` |
| Google Gemini | `google` or `gemini` | `GOOGLE_API_KEY` or `GEMINI_API_KEY` | `GOOGLE_MODEL` |

`HEALER_MODEL` is a shared fallback when a provider-specific model variable is absent. Keys may also be supplied directly to `healer.init(provider_api_key=...)` or `healer.provider(api_key=...)`; they are kept off public objects, representations, errors, and persisted traces.

```python
import healer

# Process-wide default used by healer.propose_fix(...)
healer.init(provider="anthropic", model="claude-sonnet-4-5")

# Or make an independent adapter.
fast_model = healer.provider("groq", model="openai/gpt-oss-20b")
result = fast_model.generate("Return one release-note sentence.")
print(result.text, result.total_tokens)
```

Every provider returns the same `Generation` shape and records its call as a redacted `LLM` span. `propose_fix` uses the configured default provider, but still accepts an explicit provider or a caller-supplied completion callback for tests and custom gateways.

## Install and run

Python 3.12 is the supported hackathon runtime.

```bash
cd backend
make setup
test -e .env || cp .env.example .env  # load it with your preferred secret manager; do not commit it
make test
make demo
```

The demo is deterministic and needs no live credentials. It traces a deliberately flawed research agent, finds a repeated tool call, groups the cause, generates a constrained patch, tests it against visible and sealed cases, and writes reports beneath `evidence/demo/`. Unknown costs and business values remain `TBD`.

## Docker and EC2

The production image runs a small read-only HTTP service on port `8080`. It installs all four provider adapters, runs as a non-root user, stores the local trace fallback under `/data`, and refuses protected API traffic unless `HEALER_SERVER_TOKEN` is configured.

```bash
docker build -t spectre-healer:local .
docker run --rm -p 8080:8080 \
  -e HEALER_SERVER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  -e HEALER_PROVIDER=openai \
  -e HEALER_MODEL=gpt-5-mini \
  -e OPENAI_API_KEY \
  -v healer-data:/data \
  spectre-healer:local
```

The public `/healthz` and `/readyz` routes are suitable for Docker and load-balancer health checks. Authenticated endpoints are `GET /v1/status`, `GET`/`POST /v1/scan`, `GET /v1/doctor`, and `POST /v1/resolutions`. See the complete [EC2 and ECR deployment guide](deploy/ec2/README.md) and hardened [Compose definition](deploy/ec2/compose.yaml).

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

`healer.propose_fix(...)` sends only redacted findings and cause groups to the configured provider (or a caller-supplied completion function). It accepts only JSON containing a unified diff, rejects path traversal and files outside `allowed_files`, and writes the proposal under `.healer/proposals/` without touching source files.

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
- OpenAI, Groq, Anthropic, and Google Gemini: official SDK adapters behind one redacted generation interface.
- Entire: existing CLI status and prior-session search. Entire is already enabled in this repository; approve the Codex hooks locally so commits receive checkpoints.
- cfo.ai: measured rates and costs are written to `business/inputs.json`; pricing, revenue, runway, and scenarios stay `TBD` for the user to complete in cfo.ai.

Crustdata is not in the runtime path yet because no core SDK feature needs external people/company data. GEPA is available through the optional adversary API; live provider and linked-agent execution still need verification and a controlled runner.

## Safety and privacy

- Read-only by default; no branch, patch, commit, remote write, or PR without an explicit API call.
- Secrets, bearer tokens, AWS keys, emails, phone numbers, and payment-card-like values are stripped before local persistence and model calls.
- No analytics or product tracking.
- Every score is calculated from executed cases. Missing measurements are `TBD`, never estimates presented as fact.

See [`SPEC.md`](SPEC.md) for the product contract and [`hackathon.md`](../hackathon.md) for the dated build/evidence log.
