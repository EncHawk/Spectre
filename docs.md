# Spectre architecture and developer guide

Spectre collects AI agent traces, runs deterministic checks, and helps an operator investigate observed failures. The current signed-in workspace starts with a NeatLogs connection: a user saves a service-account read token, chooses a project and a workflow found in its traces, then inspects runs and findings. The Python SDK also supports local instrumentation, repository-aware Doctor reports, example agents, and opt-in repair APIs.

## The active data path

1. The Next.js app signs a user in with Google and stores a hashed session in its SQLite database. `/app` requires that session.
2. The user supplies a NeatLogs service-account token in `/app`. The Next server encrypts it with `SPECTRE_ENCRYPTION_KEY` before saving it; browser APIs return connection status, project names, and selected workflows, never the saved token.
3. Next asks the Python service to list projects and distinct trace `workflowName` values. It saves selected `(project_id, workflow_name)` pairs for that user.
4. A report request checks ownership of the selected pair, then calls Python `POST /v1/neatlogs/doctor`. The Python service reads NeatLogs with the user's token and caches redacted traces by user, project, workflow, and trace ID. Subsequent syncs request traces from five minutes before the last successful sync to cover late arrivals and deduplicate by trace ID.
5. Doctor runs deterministic checks over the cached traces. The browser shows runs, findings, and a copyable handoff. `POST /v1/neatlogs/investigations` analyzes a selected finding and returns evidence, a likely-cause hypothesis, a suggested fix, and verification steps. This path does not edit source code.

The NeatLogs token needs `context:read` and `observability:read` for the projects bound to its service account. The Next server calls the Python service with `HEALER_SERVER_TOKEN`; the browser never receives that service token. The Python service also offers SDK/local-trace routes, repository-aware Doctor reports, bundled LangGraph examples, and a Postgres-backed project-key control API. Those are separate paths from the NeatLogs workspace above.

## Source map

| Path | Responsibility |
| --- | --- |
| `frontend/app/app/page.tsx`, `frontend/components/neatlogs-workspace.tsx` | Signed-in NeatLogs project, workflow, run, and finding views. |
| `frontend/app/api/neatlogs/` | Session and ownership checks; connection, discovery, report, and investigation routes. |
| `frontend/lib/server/auth.ts`, `db.ts`, `neatlogs.ts` | Sessions, SQLite schema and token encryption, saved NeatLogs connections, backend requests. |
| `frontend/lib/server/backend.ts`, `control.ts`, `github.ts` | Python service URL, project-key control calls, and GitHub integration. |
| `backend/src/healer/server.py` | HTTP routes, bearer-token checks, service orchestration. |
| `backend/src/healer/neatlogs_client.py`, `neatlogs_cache.py` | NeatLogs Public API reads and incremental redacted trace cache. |
| `backend/src/healer/doctor.py`, `checks.py`, `investigation.py` | Report construction, deterministic findings, and suggested investigation. |
| `backend/src/healer/runtime.py`, `store.py`, `privacy.py` | Python SDK instrumentation, local trace storage, and redaction. |
| `backend/src/healer/repository_ingest.py`, `code_graph.py` | Pinned repository snapshots and candidate Python source locations for the repository-aware path. |
| `backend/src/healer/control_db.py`, `backend/db/` | Postgres projects and hashed API keys. |
| `backend/tests/`, `frontend/tests/smoke.py` | Python unit and HTTP tests, plus frontend HTTP smoke coverage. |

The frontend still contains GitHub, project-key, example-lab, and older agent routes. They support other flows; they are not prerequisites for the current `/app` NeatLogs view. `frontend/lib/sample-data.ts` and some components are retained for those legacy/demo views. Untracked files in a checkout are local work and are not part of this guide's source map.

## Run locally

Use the service-specific templates in `backend/.env.example` and `frontend/.env.example`. Keep secrets in `backend/.env` and `frontend/.env.local`.

```sh
make setup
make migrate
make serve
# In a second terminal
cd frontend && npm install && npm run dev
```

Set the same `HEALER_SERVER_TOKEN` on both services. Set `HEALER_API_URL=http://127.0.0.1:8080` in the frontend environment for a local Python service. The frontend otherwise uses its configured hosted backend. The frontend also needs Google OAuth credentials, an allowed email, `SPECTRE_ENCRYPTION_KEY`, and a writable `SPECTRE_DB_PATH`; the Python service owns `DATABASE_URL` and provider keys. See [README.md](README.md), [backend/README.md](backend/README.md), and [backend/INTEGRATION_HANDOFF.md](backend/INTEGRATION_HANDOFF.md) for the broader SDK and control-plane flows.

## Checks

```sh
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check src tests examples db
cd ..
cd frontend && npm run typecheck
```

Database integration tests need `TEST_DATABASE_URL`. The frontend HTTP smoke script is in `frontend/tests/smoke.py` and needs a running Next server. Neither local unit tests nor TypeScript typechecking proves that live Google, GitHub, NeatLogs, or provider credentials work.
