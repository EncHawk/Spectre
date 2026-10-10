# Hackathon build log

This log records what was built, what was actually run, and what remains unverified. Numbers only appear when produced by a local or credentialed run.

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
