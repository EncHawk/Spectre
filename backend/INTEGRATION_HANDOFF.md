# Spectre control-plane integration handoff

Updated 2026-10-12. This is the copyable implementation and verification spec for a coding agent.

Run Python and migration commands from `backend/`. Service configuration lives in the ignored `backend/.env`; run `make migrate` before starting the backend with `make serve`.

## User flow

1. User opens `/app` and signs in with Google. The Next server completes OAuth authorization-code + PKCE, fetches Google's userinfo, requires a verified email, and issues a 30-day opaque HttpOnly session cookie. A SHA-256 hash of the session token is stored in SQLite.
2. User connects GitHub through the OAuth web flow. The Next server checks a state cookie tied to the signed-in user, exchanges the code, reads `/user`, and encrypts the access token with AES-256-GCM before persistence.
3. User enters `owner/repository`. The server checks access through GitHub's repository endpoint, pins its default branch commit, and ingests the recursive Git tree. It sends the OAuth token once to the authenticated Python service, which fetches that exact commit into a checkout under `HEALER_REPO_REGISTRY`; the service never persists the token. The Next control plane persists paths and sizes only. The snapshot rejects truncated trees and repositories with more than 20,000 files.
4. User defines an agent with a stable `app_id`, display name, purpose, and optional ingested repository. `app_id` must match the value in `healer.session(app_id, session_id)` in the instrumented Python agent.
5. User selects the agent. The Next route calls Python `GET /v1/doctor?app_id=...&user_id=...&repository=...&commit_sha=...` with the server-only `HEALER_SERVER_TOKEN`. Doctor indexes the selected pinned checkout and returns actual trace and finding counts, a redacted run list including successful traces, candidate Python symbols, an observed span invocation path, possible static Python calls, suggestions, trace links, and a copyable handoff for coding agents. It says “No findings” when the result is empty. Run detail is bounded to 100 spans and 1,000 characters per span input/output.
6. In the **LangGraph red team lab**, a signed-in user runs one of two allowlisted fixture agents from the frontend. Next forwards to Python, which invokes flawed and repaired LangGraph variants under Specter instrumentation. The UI shows task-contract scores, generic scanner checks, answers, observed steps, and trace IDs.
7. In the **Investigation** tab, the user can request a likely cause, suggested fix, and replay plan for an observed finding. Python reads bounded candidate source files from the pinned checkout and separates measured trace evidence from a hypothesis. OpenAI refines the answer when configured; a rule-based answer works without a model. The action does not write a patch.
8. The optional Python GEPA adversary evolves prompts before or after a measured failure. Its caller supplies an agent runner and task-contract probe; only executed contract failures count. No arbitrary linked agent can be launched from the frontend yet.

## Running locally

Requires Node >=22.13 and Python 3.12–3.13. Set the Python service's `HEALER_SERVER_TOKEN`, local log, and `HEALER_REPO_REGISTRY=.healer/repositories` as in `frontend/DOCTOR_HANDOFF.md`, then run `healer serve --host 127.0.0.1 --port 8080`.

Install the LangGraph extra in the Python environment with `pip install -e '.[lab,openai,neatlogs]'`. Add `gepa` to the extras to use the optional prompt adversary. Set `OPENAI_API_KEY` and `OPENAI_MODEL` (or `HEALER_MODEL`) on the Python service to enable model-assisted investigations; set `GEPA_REFLECTION_MODEL` and that model's provider credentials for GEPA. Set `NEATLOGS_API_KEY` there to export traces; set `NEATLOGS_TOKEN` and `NEATLOGS_PROJECT_ID` for read access. Keep all keys off the Next browser bundle. The lab and rule-based investigations work from local traces without model or Neatlogs credentials.

In `frontend/.env.local`, set:

```dotenv
SPECTRE_PUBLIC_URL=http://localhost:3000
SPECTRE_DB_PATH=.spectre/control.sqlite
SPECTRE_ENCRYPTION_KEY=<64 hex characters from openssl rand -hex 32>
SPECTRE_ALLOWED_EMAIL=<the single Google account allowed to view this workspace>
GOOGLE_OAUTH_CLIENT_ID=<Google web application client ID>
GOOGLE_OAUTH_CLIENT_SECRET=<Google client secret>
GITHUB_OAUTH_CLIENT_ID=<GitHub OAuth app client ID>
GITHUB_OAUTH_CLIENT_SECRET=<GitHub client secret>
HEALER_API_URL=http://127.0.0.1:8080
HEALER_SERVER_TOKEN=<same value used by the Python service>
```

Register these exact callback URLs in provider consoles:

- Google: `http://localhost:3000/api/auth/google/callback`
- GitHub: `http://localhost:3000/api/auth/github/callback`

Use the production HTTPS origin in `SPECTRE_PUBLIC_URL` and register the corresponding HTTPS callbacks before deployment. `SPECTRE_DB_PATH` and `HEALER_REPO_REGISTRY` must be on persistent storage; the encryption key must stay stable and secret. `SPECTRE_ALLOWED_EMAIL` is mandatory because the current Python trace store is one workspace, not tenant partitioned. SQLite and the local checkout registry are single-instance stores. Migrate to tenant-partitioned trace storage and shared storage before supporting multiple customer accounts or scaling to multiple instances.

Keep `HEALER_API_URL` on loopback in a single-host deployment, or use a private TLS connection: the one-time checkout registration sends the GitHub OAuth token from Next to Python. Do not expose the Python service bearer token or checkout registration route to browsers.

Google requests `openid email profile`. GitHub OAuth requests `repo read:user`; GitHub's `repo` scope is broad because OAuth Apps lack per-repository read-only selection. For production least-privilege access, migrate the GitHub connection to a GitHub App with repository selection and contents read permission.

## API contracts

All app endpoints require `spectre_session`; POST endpoints also require a matching `Origin` header.

| Endpoint | Action | Result |
| --- | --- | --- |
| `GET /api/me` | Signed-in user and GitHub connection | `{user, github}` |
| `POST /api/auth/logout` | Revoke current session | 303 to `/` |
| `GET /api/repositories` | List this user's snapshots | `{connected, repositories}` |
| `POST /api/repositories` | `{repository: "owner/name"}` | 201 `{repository}` pinned to a SHA |
| `GET /api/agents` | List this user's agents | `{agents}` |
| `POST /api/agents` | `{app_id,name,description,repository_id}` | 201 `{agent}`; same app ID updates definition |
| `GET /api/doctor?app_id=<id>` | Join user-owned agent to Python Doctor report | `{agent,repository,trace_count,finding_count,rows,runs}` |
| `GET /api/examples` | List two allowlisted LangGraph fixture agents | `{examples}` |
| `POST /api/example-runs` | `{example: "checkout_support" \| "research_brief"}` | Before/after contract results and trace IDs |
| `POST /api/investigations` | `{app_id,finding_id}` for an observed finding | Evidence, likely cause, suggested fix, verification plan |
| `POST /api/proposals` | Legacy API for a linked repository | Draft diff; not used by the Investigation UI |

Python adds `POST /v1/repositories` for a pinned checkout and accepts `user_id`, `repository`, and `commit_sha` filters on `GET /v1/doctor`. It also serves `GET /v1/examples`, `POST /v1/example-runs`, `POST /v1/investigations`, and the legacy `POST /v1/proposals`. These routes require the service bearer token and should be reachable only from the trusted Next server. The investigation route checks the finding against that agent's observed traces and uses the signed-in user's pinned checkout when present.

The UI labels the cause as likely and offers a way to verify it. It does not claim the suggestion was tested. The existing Python resolution and PR validation flow remains separate.

## Measured LangGraph black-box result

`checkout_support` executes route → policy → gateway → optional ledger fallback → verify → respond. A timeout and a pressure instruction expose a false success claim. Contract passes improved from **1/3 to 3/3**. The generic `ignored_error` check catches the gateway timeout, but it does not prove whether the final claim is correct.

`research_brief` executes plan → retrieve → synthesize → verify evidence → respond. Missing citations and an injected retrieved instruction expose unsupported claims. Contract passes improved from **1/3 to 3/3**. The generic `claim_without_source` check misses the injected case because a retrieval span exists; the citation and evidence contract catches it.

These runs use deterministic fixture tools inside real LangGraph graphs. They validate Specter's run/trace/scanner path and domain-contract scoring, not live payment or research services. In the tested environment, six runs per example were recorded locally. No Neatlogs export or OpenAI request was made because provider credentials were absent. The source graph for this checkout indexed 239 Python symbols and 394 possible call edges; those edges are AST hypotheses. One Doctor finding showed the observed path `checkout_support → charge_gateway`.

## Executable agent testing handoff

Selecting an arbitrary linked agent still does not launch its repository code. The new frontend run button executes only two allowlisted fixture graphs. To add the requested in-product “test, then hand off” run flow for user repositories, implement these steps as a separate job service:

1. Extend agent definitions with a reviewed test entrypoint and named secret references. Do not accept an arbitrary shell command from a browser request.
2. Add `POST /api/agents/{id}/test-runs` and `GET /api/agents/{id}/test-runs/{runId}`. Authorize the agent and its pinned repository SHA before enqueueing. Return a job ID immediately.
3. Run each job in an isolated, disposable worker with network and resource limits. Mount the pinned checkout read-only, inject only explicitly approved secrets, and set a timeout. Record the exact commit, command, exit code, test counts, log digest, and trace IDs. Never mark a timeout or missing trace as a pass.
4. Join the measured result with Doctor findings. Produce a structured summary with pass/fail counts, failing trace IDs, candidate code locations, and a copyable coding-agent prompt. Keep raw logs separate and redact secrets before display.
5. Give a future adversary trigger access only to a reviewed agent entrypoint and its task contract. Show each executed prompt, contract result, and trace ID next to the investigation. Do not count a model's unevaluated candidate as a failure.

This run service needs an execution sandbox and is not part of the current repository checkout and diagnostics connection.

## Verification completed

- `npm run typecheck` — passed.
- `npm run build` — passed; OAuth, agent, repository, Doctor, and investigation routes compiled.
- `PYTHONPATH=.:src .venv/bin/pytest --ignore=tests/test_competitor_agent.py -q` — passed the project suite, including the investigation API and a real GEPA search probing a traced LangGraph agent. The untracked `plus_usage/` experiment and its test were excluded from this verification.
- A local service run recorded six checkout-support traces and four findings, then returned an investigation for one `ignored_error` finding with matching trace ID and a rule-based suggestion.
- `PYTHONPATH=.:src .venv/bin/python -m examples.langgraph_lab` — both agents returned 1/3 before and 3/3 after.
- `python3 frontend/tests/smoke.py` — passed session auth, CSRF, agent ownership, Doctor bridge, example-run bridge, investigation bridge, and repository snapshot read against a mock Python service. The localhost bind required the permitted network sandbox escalation.

## Remaining live verification

Real OAuth credentials were not available in this workspace, so Google/GitHub consent, provider code exchange, and a live private repository ingest have not been verified. Once credentials are supplied, sign in, connect GitHub, ingest a repository, save an agent, instrument a trace using its `app_id`, and confirm the finding and copied handoff in `/app`. Verify GitHub organization approval if the target repository is organization owned.

Doctor now indexes a selected pinned checkout for an OAuth-connected agent. Its AST name matches are navigation hints, not proof of root cause. The checkout fetch needs storage and network capacity appropriate for the repository; large repositories may exceed the current 120-second Git timeout. Treat trace text and copied handoffs as untrusted input to coding agents.
