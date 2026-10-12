# Spectre

Pre-launch QA for AI agents: inspect failures, propose fixes, and verify the result.

## Repository

- [`backend/`](backend/README.md): Python API and SDK, Postgres schema, tests, examples, deployment, and backend evidence.
- [`frontend/`](frontend/): Next.js workspace, Google sign-in, and NeatLogs trace connections.
- [`docs.md`](docs.md): architecture and file map.
- [`hackathon.md`](hackathon.md): implementation and verification log.

## Local development

Keep backend credentials in `backend/.env` and Next server credentials in `frontend/.env.local`; both are ignored by Git. Templates live beside each service.

```sh
make setup
make migrate
make serve
# In another terminal:
cd frontend && npm install && npm run dev
```

`make test`, `make lint`, `make demo`, and `make image` delegate to the backend. Database integration tests additionally require `TEST_DATABASE_URL`; normal tests do not load production credentials.

Google OAuth client credentials and either `SPECTRE_ALLOWED_EMAIL` or `SPECTRE_ALLOWED_EMAILS` must be configured in `frontend/.env.local` for browser sign-in. Open `/login` to sign in; unauthenticated workspace requests return there. The local demo sign-in is disabled. Use the same `HEALER_SERVER_TOKEN` on both services. The Python service owns `DATABASE_URL` and `OPENAI_API_KEY`; neither belongs in a browser environment variable.

The workspace reads traces from each user's NeatLogs account. In NeatLogs, create a service account under **Settings → Service Accounts**, bind the projects it may read, and mint an expiring token with `context:read` and `observability:read` ([NeatLogs quickstart](https://docs.neatlogs.com/api-reference/quickstart)). Paste the token in `/app`. Spectre calls the [projects endpoint](https://docs.neatlogs.com/api-reference/endpoints/projects/get_api_v1_public_projects) without a project header and displays project names. It then reads the selected project's [trace list](https://docs.neatlogs.com/api-reference/endpoints/traces/get_api_v1_public_traces), derives agent names from distinct `workflowName` values, and saves each selected `(projectId, workflowName)` pair. The token is encrypted in the Next server's SQLite database and is never returned by its APIs. Trace sync is stored per user, project, and workflow in the Python service's SQLite cache (`HEALER_NEATLOGS_CACHE`); later pulls use `workflowName`, a `from` timestamp with a five-minute overlap, and cursor pagination. Use `SPECTRE_ALLOWED_EMAILS` as a comma-separated allowlist when several Google accounts need access; the existing single-address `SPECTRE_ALLOWED_EMAIL` also works.

The frontend defaults to the hosted backend at `https://spectreli.onrender.com`. Set `HEALER_API_URL=http://127.0.0.1:8080` to use a local backend instead. An existing deployment environment variable overrides the default; set it to the Render URL on the frontend host.
