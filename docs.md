# Spectre, in one read

Spectre helps a team understand why an AI agent failed and prepare a safer fix. The intended loop is:

**Run an agent → record its steps → find a failure → investigate the trace and related code → suggest a fix and a way to verify it.**

Today, the Python SDK handles tracing, checks, test cases, investigations, and an optional GEPA adversary loop. The web app handles sign-in, GitHub repository snapshots, agent definitions, run inspection, two runnable LangGraph examples, and investigation requests. Older repair and PR functions remain in the SDK. A linked agent's own code must already send traces to Spectre; linking it in the UI does not execute that repository.

## What someone can do today

1. **Connect:** Sign in with Google, connect GitHub, pin a repository commit, and define an agent with an `app_id`.
2. **Observe:** Instrument an agent with `healer.agent`, `healer.tool`, and `healer.session(app_id, session_id)`. Spectre records redacted spans locally and can send/read Neatlogs traces when configured.
3. **Investigate:** Select the agent in the web app to see successful and failed runs, steps, findings, code candidates, an observed invocation path, possible Python call edges, and a summary to copy into a coding agent.
4. **Challenge it:** Run the checkout-support and research-brief LangGraph examples from the web app. Each compares flawed and repaired behavior against three task contracts. Both scored **1/3 before and 3/3 after** in local tests. These examples use fixture tools, not live payment or research services.
5. **Suggest a fix:** In the Investigation tab, select a finding. Spectre uses its measured trace, candidate code, and possible call edges to return a likely cause, suggested fix, and replay plan. OpenAI can refine the explanation when configured; otherwise a rule-based suggestion appears. No code is changed.
6. **Evolve attacks:** A developer can call `evolve_prompts` with an agent runner and task-contract probe. GEPA searches for prompts that produce measured contract failures, either before a known failure or using one as context. This is a Python API; the frontend does not launch arbitrary linked agents yet.

The scanner detects repeated calls, ignored errors, missing recovery, loops, empty answers, unsupported claims, missing lookups, and unusual cost. A task-specific contract can catch failures the generic scanner misses, such as a retrieved page injecting an unsupported claim.

## What remains to build or verify

- **Run any linked repository agent from the UI:** needs an isolated job worker, a reviewed entrypoint, secret references, limits, and captured test results. The current run button is for the two bundled examples.
- **Run an adversary against any linked agent from the UI:** needs the same controlled job runner plus a task-specific pass/fail contract. The current GEPA loop is callable from Python with a supplied probe.
- **Live integrations:** the local tests and frontend smoke pass. Google/GitHub consent, private repository ingest, Neatlogs export, and an OpenAI request still need real credentials and live checks.
- **Production scale:** the current SQLite control plane and local trace/checkout stores are single-instance. The Docker image installs provider and Neatlogs extras but currently omits the optional LangGraph `lab` extra.

## Technology in plain English

| Layer | Technology | Why it is here |
| --- | --- | --- |
| Agent SDK and API | Python 3.12+, standard-library HTTP server | Wrap agent/tool calls, store traces, scan failures, expose results. |
| Trace service | Neatlogs, with a redacted JSONL fallback | Capture and inspect execution steps. |
| Example workflows | LangGraph | Show real multi-step graph execution and red-team comparisons. |
| Investigation | OpenAI Responses API with a rule-based fallback | Explain likely causes and suggest a fix and verification from measured evidence. |
| Adversary | GEPA optional extra and a caller-supplied contract probe | Evolve prompts and count only executed contract failures. |
| Web app | Next.js, React, TypeScript, Tailwind CSS | Account connection, repository/agent setup, run and finding views. |
| Identity and data | Google OAuth, GitHub OAuth, SQLite, encrypted GitHub token | Sign-in, repository access, and agent definitions. |
| Shipping and quality | Docker, EC2/ECR guide, pytest, Ruff, frontend smoke test | Run the API and check behavior. |

## Directory and file guide

Files below are the **tracked project files**, grouped so the map stays readable. Names within a row share the purpose shown at right.

| Directory | Files | Purpose |
| --- | --- | --- |
| Root | `docs.md`, `README.md`, `INTENT.md`, `hackathon.md` | This overview, technical guide, original idea, and build log. |
| `backend/` setup | `pyproject.toml`, `uv.lock`, `Makefile`, `Dockerfile`, `.env.example`, `.dockerignore` | Python dependencies, commands, image, and configuration templates. Root Makefile delegates backend commands. |
| Tool metadata | `.codex/hooks.json`, `.entire/settings.json`, `.entire/.gitignore` | Local Codex and Entire integration settings. |
| `backend/` | `SPEC.md`, `DOCTOR.md`, `INTEGRATION_HANDOFF.md` | Product contract, Doctor notes, and the detailed developer handoff. |
| `backend/business/` | `inputs.json` | Measured business inputs; unknown business values remain unset. |
| `backend/deploy/ec2/` | `README.md`, `compose.yaml`, `.env.example` | EC2/ECR deployment steps, Compose settings, and server env template. |
| `backend/evidence/` | `.gitkeep`; `demo/report.json`, `demo/report.md`, `demo/runs.jsonl` | Kept demo traces and reports. |
| `backend/examples/research_agent/` | `agent.py` | Small deliberately flawed agent for the basic demo. |
| `backend/examples/langgraph_lab/` | `__init__.py`, `__main__.py`, `README.md` | Runnable entry point and explanation for the two graph examples. |
| `frontend/` | `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.ts`, `next-env.d.ts`, `postcss.config.mjs`, `.gitignore`, `AGENTS.md`, `DOCTOR_HANDOFF.md` | Web dependencies, build configuration, local rules, and UI handoff. |
| `frontend/app/` | `layout.tsx`, `page.tsx`, `globals.css` | Global layout, public landing page, and styles. |
| `frontend/app/app/` | `layout.tsx`, `page.tsx`; `investigation/page.tsx`, `sessions/page.tsx`, `sessions/[sessionId]/page.tsx` | Signed-in shell, Investigation tab, and control-plane routes. |
| `frontend/app/api/auth/google/` | `start/route.ts`, `callback/route.ts` | Google sign-in start and callback. |
| `frontend/app/api/auth/github/` | `start/route.ts`, `callback/route.ts` | GitHub connection start and callback. |
| `frontend/app/api/auth/logout/` | `route.ts` | End the signed-in session. |
| `frontend/app/api/` | `me/route.ts`, `repositories/route.ts`, `agents/route.ts`, `doctor/route.ts` | Current user, pinned repositories, agent definitions, and Doctor report. |
| `frontend/app/api/` | `backend/examples/route.ts`, `example-runs/route.ts`, `investigations/route.ts`, `proposals/route.ts` | List/run bundled graphs, request an investigation, and retain the older draft API. |
| `frontend/components/` | `control-plane.tsx`, `investigation-panel.tsx`, `observed-runs.tsx`, `example-lab.tsx`, `approval-panel.tsx`, `session-list.tsx`, `status-pill.tsx` | Main workspace, investigation results, run detail, red-team lab, and supporting views. |
| `frontend/components/` | `dashboard-shell.tsx`, `marketing-home.tsx`, `repository-prompt.tsx`, `logo.tsx` | Navigation, landing page, repository prompt, and branding. |
| `frontend/components/reactbits/` | `aurora.tsx`, `blur-text.tsx`, `magnet.tsx` | Visual effects on the public site. |
| `frontend/lib/` | `sample-data.ts` | Legacy presentation data; the control plane uses backend data. |
| `frontend/lib/server/` | `auth.ts`, `backend.ts`, `db.ts`, `github.ts` | Session/security helpers, Python API bridge, SQLite, and GitHub API logic. |
| `frontend/public/images/` | `spectre-foreground-mountain.png`, `spectre-meadow.png`, `spectre-river-base-v2.png`, `spectre-river-fantasy.png`, `spectre-valley-base.webp`, `spectre-valley-near.webp`, `spectre-valley.png` | Public site artwork. |
| `frontend/tests/` | `smoke.py` | Local HTTP test for auth, ownership, Doctor, example runs, and investigations. |
| `backend/src/healer/` | `__init__.py`, `__main__.py`, `cli.py`, `server.py` | Public SDK, module entry point, CLI, and Python HTTP API. |
| `backend/src/healer/` | `runtime.py`, `models.py`, `store.py`, `privacy.py`, `timeutil.py`, `errors.py` | Instrumentation, data types, local storage, redaction, time parsing, and errors. |
| `backend/src/healer/` | `neatlogs_client.py`, `scanner.py`, `checks.py`, `causes.py` | Neatlogs reads, finding generation, individual checks, and cause grouping. |
| `backend/src/healer/` | `doctor.py`, `investigation.py`, `code_graph.py`, `repository_ingest.py` | Join runs to repository context, explain findings, infer possible Python calls, and fetch pinned GitHub checkouts. |
| `backend/src/healer/` | `lab_agents.py`, `lab_runner.py`, `adversarial.py`, `adversary.py`, `replay.py` | Two LangGraph agents, their test runner, attack inputs, GEPA prompt search, and tool replay. |
| `backend/src/healer/` | `fixes.py`, `regression.py`, `pull_request.py`, `report.py`, `demo.py`, `sponsors.py` | Draft/apply fixes, score changes, guard PRs, create reports, run demo, and export sponsor inputs. |
| `backend/src/healer/` | `dashboard.html`, `dashboard.css`, `dashboard.js` | Small operator dashboard served by the Python API. |
| `backend/src/healer/providers/` | `__init__.py`, `base.py`, `registry.py`, `openai.py`, `groq.py`, `anthropic.py`, `google.py` | Shared model interface and provider adapters. |
| `backend/tests/` | `test_adversary.py`, `test_checks.py`, `test_code_graph.py`, `test_doctor.py`, `test_flows.py`, `test_investigation.py`, `test_langgraph_lab.py`, `test_neatlogs_client.py`, `test_privacy.py` | Adversary, scanner, graph, Doctor, repair loop, investigation, lab, Neatlogs, and redaction tests. |
| `backend/tests/` | `test_providers.py`, `test_repository_ingest.py`, `test_runtime.py`, `test_server.py`, `test_store_ids.py`, `test_time_store.py` | Provider, checkout, tracing, API, ID, and time/storage tests. |

Local folders such as `backend/.venv/`, `frontend/node_modules/`, `frontend/.next/`, `backend/dist/`, `backend/.healer/`, `backend/.pytest_cache/`, `backend/.ruff_cache/`, and `.entire/logs/` are generated dependencies, builds, traces, or caches. The untracked `backend/plus_usage/` experiment (`__init__.py`, `agent.py`, `checks.py`, `README.md`, `requirements.txt`) and `backend/tests/test_competitor_agent.py` are separate local work, not part of the shipped source inventory.

For setup commands and API details, read [README.md](README.md). For the exact frontend/backend contract and the remaining job-runner work, read [backend/INTEGRATION_HANDOFF.md](backend/INTEGRATION_HANDOFF.md).
