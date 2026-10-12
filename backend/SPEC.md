# Spectre SDK

A Python SDK. You set one neatlogs API key. Healer reads your agent's traces with that key, finds the mistakes, fixes them, proves the fix works, and opens a PR.

It must work on any agent that sends traces to neatlogs, not just the demo agent.

## How someone uses it

```python
import healer

healer.init()                      # reads the neatlogs API key from env
findings = healer.scan(since="24h")  # finds mistakes in their traces
for f in findings:
    print(f.reason, f.trace_url)
```

Going further (needs more access):
- Give it a repo path and it proposes a fix on a branch.
- Give it a function that runs their agent and it tests the fix, then opens a PR.

## Rules

1. Never make up results. Every number must come from a real run. If it isn't measured, write TBD.
2. Never put keys in git or logs. Use env vars and a `.env.example`.
3. Don't guess how neatlogs, Entire, Crustdata, or AWS deployment works. Read their docs first. If something isn't documented, note it in `hackathon.md` and use the fallback.
4. The SDK must not depend on the demo agent.
5. Read-only by default. Writing to git or opening PRs only happens when the user says so.
6. All code is written during the hackathon. Commit often.
7. Every commit gets an Entire checkpoint. Set this up first.
8. Trace everything with neatlogs, including Healer's own LLM calls.
9. Keep a log of what was built in `hackathon.md`, updated after every work session.

## Setup defaults

- Python 3.12, pytest, a Makefile with `setup`, `test`, `demo`.
- neatlogs for tracing (`pip install -U neatlogs`, `neatlogs.init()`).
- OpenAI, Groq, Anthropic, or Google for the models Healer uses to analyze and fix. Provider credentials are separate from the neatlogs key.
- A hardened Docker image and read-only HTTP API deployable to an Amazon Linux 2023 EC2 instance through ECR.
- Folders: `src/healer/` (the SDK), `examples/research_agent/` (demo), `tests/`, `evidence/`, `business/`.

## Features

**Core**
1. **Connect with one key.** `healer.init()` takes the neatlogs key and checks what it can do: send traces, read traces. If it can't read, say exactly what's missing, and fall back to a local run log so scanning still works.
2. **Wrap an agent.** A decorator that traces any agent function and tags each run.
3. **Read traces.** Fetch traces by time, tag or ID. Handle pages and rate limits.
4. **Scan for mistakes.** Read recent traces and report problems with the span, reason, and a link. Needs no setup from the user.
5. **Built-in checks.** Repeated tool calls, errors ignored, no recovery after a failure, loops, cost spikes, empty answers, claims with no source, answering without looking anything up.
6. **Turn mistakes into tests.** Each finding becomes a test case that fails today.
7. **Find the cause.** Group mistakes by cause and decide where the fix belongs: prompt, tool code, or rules.
8. **Propose a fix.** Edit only the right files on a new branch. By default, just write the diff and touch nothing.
9. **Test the fix.** Re-run the failing cases and the full test set on the fixed version. Accept only if it clearly improves and breaks nothing. Keep rejected fixes and the reason.
10. **Open a PR.** Only when the user asks. PR shows real before and after numbers.
11. **Report.** One file with before and after results, trace IDs, and cost.
12. **Command line.** Same things from the terminal, with `--json` and `--dry-run`.
13. **Install and docs.** `pip install`, a 10-line quickstart, a demo agent in `examples/` with built-in flaws.
14. **Privacy.** Strip secrets and personal data before sending anything to a model. No tracking. Test it.
15. **Clear errors.** Plain messages for bad keys, missing access, rate limits.

**Break it on purpose**
16. **Variants.** Rephrase, add noise, make inputs ambiguous.
17. **Attacker.** A second model tries to break the agent. It must be a different model family than the agent it attacks.
18. **Sealed test set.** Hidden attack tests that the fixer can never see, used only for final scoring. Report seen and hidden results separately.
19. **Fault injection.** Force tool failures (rate limits, empty results, bad data) and record how the agent recovers.
20. **Replay.** Record tool outputs and replay a run from a chosen step with the fixed agent.

**Sponsor tools**
21. **neatlogs Fixes check.** Pull neatlogs' fix suggestions, test each one, and only accept the ones that pass.
22. **Entire memory.** Before proposing a fix, search past sessions for similar failures and rejected tries.
23. **Entire code map.** Use entire-graph to find which code caused a failing step.
24. **Entire checkpoints.** Attach one to every commit.
25. **cfo.ai numbers.** Produce measured costs and success rates in `business/inputs.json`. The user builds the actual plan in cfo.ai (pricing, costs, revenue, runway, two scenarios).

**Ship**
26. **Build log.** Keep `hackathon.md` current: dated changes, failures, fixes, evidence. Follow https://neatlogs.com/hackathon/skill.
27. **One-command demo.** `make demo` from a clean clone with only the key set: scan, find causes, fix, test, hidden test, report. Short enough to explain in under 3 minutes.

**Only if everything else is done:** GEPA prompt optimizer, a second demo agent on a different framework, Claude Code or Codex as the fixer.

## Build order

1. **Setup.** Repo, Entire checkpoint working, neatlogs connected, check what the key can do.
2. **Skeleton.** Features 1, 2, 3, 13 and the demo agent.
3. **Scan.** Features 4, 5, 14, 12.
4. **Fix loop.** Features 6 to 11, 24.
5. **Break it.** Features 16 to 20.
6. **Sponsor tools.** Features 21 to 23, 25.
7. **Ship.** Features 26 and 27, check the quickstart in a fresh environment.

Check that each step actually works before starting the next. If time runs short, cut from the end. Never cut steps 1 to 4, the sealed test set, the cfo.ai numbers, the build log, or the demo.

## Original scope boundary

The initial SDK scope excluded OAuth. The later control-plane implementation adds Google sign-in and GitHub OAuth repository snapshots; see `backend/INTEGRATION_HANDOFF.md`. It does not add automatic PR creation, sandbox infrastructure, unreleased neatlogs Datasets, or self-hosted neatlogs support.

## Docs to read first

- neatlogs: https://docs.neatlogs.com
- Entire: https://docs.entire.io
- Crustdata: https://docs.crustdata.com
- EC2 container image guide: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/create-container-image.html
- ECR authentication: https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html
- Hackathon rules: https://neatlogs.com/hackathon

## Evidence to keep in `evidence/`

- Before and after runs with real neatlogs trace IDs and the numbers
- A run where a tool failed and what the agent did next
- Entire checkpoints or entire-graph output
- The cfo.ai business plan
- What the neatlogs key could and couldn't do
- Links to public #neatHack posts
