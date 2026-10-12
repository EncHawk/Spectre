# Doctor frontend handoff — 2026-10-10

> Update 2026-10-12: the Next control plane now has Google login, GitHub repository snapshots, agent definitions, a server-side Doctor bridge, two runnable LangGraph fixture agents, and OpenAI draft proposals for findings on pinned checkouts. See [`backend/INTEGRATION_HANDOFF.md`](../backend/INTEGRATION_HANDOFF.md) for the current setup, observed results, and remaining live verification. The prototype notes below are retained for the original Doctor API contract.

Read this file before wiring the Next.js UI. The backend's single code reference is [`src/healer/doctor.py`](../src/healer/doctor.py); it contains the report shape, AST matching, suggestions, and repair history. The current Next.js pages under `frontend/app/app/` still use `frontend/lib/sample-data.ts`. A separate working reference UI is served by the Python service at `/app/` from `src/healer/dashboard.html` and `dashboard.js`.

## Small change log

- Added `healer.session(app_id, session_id)` to tag each instrumented chat. A session may contain several trace/run IDs.
- Added `healer.doctor(...)` and `healer doctor` to join deterministic trace findings with candidate functions in a local Git checkout. It reads Git-tracked Python files with `ast` and returns file/line links to the checked-out GitHub commit when `origin` is configured. It does **not** send or persist source bodies.
- Added `GET /v1/doctor` for the dashboard and `POST /v1/resolutions` for append-only repair notes, statuses, and existing PR links. Both require `Authorization: Bearer <HEALER_SERVER_TOKEN>`.
- Added a working dashboard served by the Python service at `/app/` with a finding table, suggestions, repair history, PR link, and **Copy to Agent**. The Next.js prototype has not been connected to this API yet.

## API contract to render

`GET /v1/doctor?since=24h&app_id=support&session_id=chat-42&limit=100`

`app_id` and `session_id` are optional filters. Response shape (values below illustrate structure, not measured data):

```ts
type DoctorReport = {
  generated_at: string;
  repository: {
    path: string;              // server checkout path
    github_url: string | null; // origin, if it is GitHub
    commit: string | null;
    indexed_files: number;
    indexed_bytes: number;
  };
  trace_count: number;
  finding_count: number;
  rows: Array<{
    finding: {
      id: string; check: string; reason: string;
      trace_id: string; span_id: string | null;
      severity: "low" | "medium" | "high" | "critical";
      trace_url: string | null; evidence: Record<string, unknown>;
      detected_at: string;
    };
    app_id: string; session_id: string; agent: string;
    trace_status: string; trace_started_at: string;
    suggestion: string;
    suggestion_basis: string; // deterministic check; code location is a name match
    candidate_locations: Array<{symbol: string; file: string; line: number; url?: string}>;
    resolution: Resolution | null;       // latest event
    resolution_history: Resolution[];   // all events, oldest first
    copy_to_agent: string;                // ready to copy verbatim
  }>;
};
type Resolution = {
  finding_id: string;
  status: "investigating" | "proposed" | "validated" | "resolved" | "rejected";
  note: string; pr_url: string | null; recorded_at: string;
};
```

`POST /v1/resolutions` body: `{ "finding_id": "<16-hex-id>", "status": "investigating", "note": "...", "pr_url": null }`. The finding must exist in recent traces. `pr_url`, when supplied, must be an existing `https://github.com/<owner>/<repo>/pull/<number>` URL. Show `resolution_history` as the fix timeline and `resolution.pr_url` in the PR column. Do not label a suggestion or user-entered status as a proven fix.

## Frontend wiring

1. Replace `sample-data.ts` in the observability view with Doctor rows. Group by `app_id`/`session_id` for session navigation, and use `finding.id` as a row key. Show trace link, reason, severity, suggestion, candidate file/line, latest status, PR link, and **Copy to Agent**. The backend only returns finding rows, so successful traces contribute to `trace_count` but do not have table rows.
2. The Next.js dev server and Python API usually run on different origins. Use a Next server route or same-origin reverse proxy for `/v1/doctor` and `/v1/resolutions`; the Python API does not expose CORS. Keep the backend URL in a server-only environment variable. Until frontend user authentication exists, have the operator supply the bearer token; do not bake `HEALER_SERVER_TOKEN` into browser code or a public `NEXT_PUBLIC_*` variable.
3. For an empty result, show “No findings in this window” and real `trace_count`/`finding_count` values. Do not reuse the prototype's sample metrics or claim a PR is ready from this endpoint.

Run locally with `HEALER_SERVER_TOKEN=<token> HEALER_LOCAL_LOG=.healer/runs.jsonl HEALER_REPO_PATH=. HEALER_RESOLUTION_LOG=.healer/resolutions.jsonl healer serve --host 127.0.0.1 --port 8080`. `GET /v1/doctor` is read-only; only an explicit resolution POST writes history. PR creation is still the separate SDK `validate_candidate(...)` → `open_pull_request(...)` flow. The dashboard should link a PR after that flow, not create an unvalidated one.
