# Hackathon build log

This log records what was built, what was actually run, and what remains unverified. Numbers only appear when produced by a local or credentialed run.

## 2026-10-12 — Project key control plane

- Added Postgres schema for users, projects, hashed project keys, and jobs with row-level security enabled and no unprivileged policies. The Python service owns key generation, lookup, and revocation. Next routes require the existing Google session and origin check before proxying to Python.
- Added a signed-in key UI with scope selection, one-time display, copy, metadata listing, and revoke. Added service-specific env templates. The server-side `OPENAI_API_KEY` remains separate from issued `HEALER_API_KEY` values. Usage cost is not calculated.
- Verified Psycopg pool and parameter binding behavior against current official docs. The spec's mentioned `schema.sql`, `keys.py`, and `test_keys.py` attachments were absent from the supplied attachment directory; this implementation follows the specified schema and key format. The exact text of those claimed attachments remains unavailable.
- Verification: Next production build and TypeScript checks passed; Python suite passed with the Postgres-only tests skipped when no test URL was set. The schema applied to an isolated local Postgres. Both real-Postgres key lifecycle and HTTP-handler tests passed with `TEST_DATABASE_URL`; the frontend smoke passed with a fake Python backend, covering missing/expired sessions, origin checks, one-time key response, and revoke. No external Postgres host or production OAuth credentials are configured.
- Added app-entry checks for the existing HttpOnly Google session and an active project key. Signed-in users without one enter `/setup` to mint and copy their key; invalid sessions return to the marketing sign-in button. Revoked and expired keys lose app entry on the next server request. The access query remains server-side and does not put key state in a client cookie.
- Verified the revised Next production build and frontend smoke: `/app` and `/app/investigation` redirect to setup before issuance, open after issuance, and redirect again after revoke. The isolated Postgres tests confirmed the active-key query before issuance, after issuance, after expiry, and after revoke. Live Google OAuth was not exercised because OAuth client credentials are not configured in this environment.

## 2026-10-10 — SDK foundation and end-to-end local proof

Built:

- Python package, CLI, Makefile, environment template, demo agent, and test suite.
- Neatlogs capability detection with separate documented ingest and Public API credentials.
- Neatlogs Public API trace and span-payload reads using the official OpenAPI contract, with cursor pagination and bounded `429` retries.
- Redacted append-only local trace fallback and sync/async agent/tool decorators.
- Eight deterministic checks covering repetition, loops, errors/recovery, empty answers, unsupported source-sensitive claims, missing lookup, and measured cost spikes.
- Finding-to-regression-case conversion, cause grouping, sealed sets, adversarial variants, different-family attacker guard, fault injection, and tool replay.
- Provider-neutral generation adapters for the official OpenAI, Groq, Anthropic, and Google Gen AI SDKs; environment-key auth, token usage normalization, and traced/redacted model calls.
- Multi-stage, non-root Docker image with authenticated read-only status/scan endpoints, health checks, persistent local traces, a hardened Compose definition, and an EC2/ECR deployment guide.
- Runtime-lazy sync/async decorators, so an agent can be defined before `healer.init()` and follows later runtime initialization.
- Read-only-by-default unified-diff proposal workflow with file allowlists and the configured provider as its default fixer.
- Candidate validation with separate visible/hidden scores; explicit git apply and PR gates.
- Neatlogs detection-suggestion reader/test harness, Entire status/search helpers, JSON/Markdown reports, and cfo.ai input generation.

Verified locally:

- 47 tests passed on Python 3.12.12, including provider adapters, pre-init decorators, and the hosted HTTP API.
- Ruff lint and formatting checks passed, and both a wheel and source distribution built successfully.
- The Docker image built successfully, started as the non-root `healer` user, reached Docker `healthy`, and returned successful `/healthz` plus bearer-authenticated `/v1/status` responses.
- The packaged demo found 1 measured repeated-tool-call failure in 1 visible case.
- The demo candidate moved visible success from 0/1 to 1/1.
- The sealed demo score moved from 0/1 to 1/1.
- The generated patch remained a proposal; the demo did not modify the example agent.
- Cost was not measured and is reported as `TBD`.

External integration status:

- Entire CLI 0.11.4 reports this repository enabled on `main` with Codex configured. Seven Codex hooks still require approval in the local UI; no claim is made that this session's commits have checkpoints until that approval occurs.
- No Neatlogs credential was present during the local proof, so live ingest/read behavior is unverified. The SDK used the documented local fallback.
- No live provider credential/model run was performed. Official SDK request shapes are covered with injected clients; the demo injects a deterministic proposal generator.
- No Git remote is configured, so no PR was opened.
- The hackathon skill URL returned an inaccessible response to the documentation client. The repository follows the build-log and evidence rules copied into `backend/SPEC.md`; anything unique to that remote skill remains unverified.

Documentation decisions:

- Neatlogs' official docs state that SDK ingest credentials do not authorize Public API reads. Healer therefore reports send/read separately instead of falsely promising both from every key.
- The official Public API uses `from`, a maximum page size of 50, opaque `nextCursor` values, and selected span payload reads. The implementation follows those fields.
- Neatlogs Fixes are exposed in the API as detection suggestions. Healer reads and tests pending suggestions but never accepts them server-side automatically.
- AWS is used only as the container hosting target; model inference remains provider-selectable and Bedrock is not part of the SDK.
- Crustdata is excluded from the runtime because this SDK currently has no feature requiring company/person/job data.

Next live-evidence session:

1. Approve the Entire Codex hooks and confirm a checkpoint on the next commit.
2. Provide Neatlogs ingest and service-account credentials through the environment, run `python -m neatlogs doctor --probe --json`, then save capability evidence without secrets.
3. Run the flawed demo through Neatlogs and retain real trace IDs plus measured costs.
4. Run a provider-generated proposal against visible and sealed cases, then deploy the immutable image digest to EC2.
5. Add the live before/after report and update `business/inputs.json` with measured costs.

## 2026-10-10 — Doctor and observability dashboard

- Added `healer.session(app_id, session_id)` so an instrumented agent run carries a chat-level identity in its trace attributes.
- Added `healer.doctor(...)` and `healer doctor`: deterministic findings joined to Git-tracked Python AST symbol locations, the checked-out commit, and a GitHub origin permalink when available. Source bodies are not copied into reports.
- Added append-only resolution records and an operator dashboard at `/app/`, with filtered chat URLs at `/app/<app-id>/<session-id>`, authenticated Doctor data, suggestions, PR links, and Copy to Agent handoffs.
- The dashboard records PR URLs after a validated fix is opened through the existing explicit PR flow. GitHub OAuth, remote checkout, and dashboard-triggered PR creation remain unimplemented.
- Verification: local pytest and Ruff checks cover identity tagging, AST matching without source disclosure, resolution validation, and authenticated API routes. Live Neatlogs and GitHub integration remain unverified without credentials and a configured remote.


## 2026-10-12 — Authenticated keys, database connection, and backend cleanup

- Moved Python source, packaging, tests, examples, deployment, evidence, business inputs, and local service configuration into `backend/`. Root Make targets delegate there; the backend uses its own Python 3.12 environment.
- Connected to the configured Postgres database and applied migration `001` transactionally. Repeating the migration verified its checksum and skipped reapplying it.
- API keys are minted by Python after authenticated Next requests; only prefixes and SHA-256 hashes are persisted. The raw key is returned once. Project ownership, revocation, expiration, and scopes are checked server-side.
- The frontend requires a valid HttpOnly-cookie session before `/app`, then requires an active API key. Signed-in users without a key are sent to `/setup`; expired sessions return to sign-in.
- Preserved real provider/database settings in ignored `backend/.env`, generated matching service tokens for Python and Next, and removed a database credential from the example template. Browser OAuth still requires Google client credentials and the allowed email in `frontend/.env.local`.
- Verification: 82 Python tests passed; 2 database-backed HTTP/key lifecycle tests passed against the configured database and cleaned up their test users. Next production build and frontend HTTP smoke checks passed, including authentication, key setup, and revocation. Backend wheel and source distribution built successfully; Ruff passed.
- No spend accounting was added. OpenAI credentials remain server-side.
