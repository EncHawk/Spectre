"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Check, Copy, FlaskConical, ScanSearch } from "lucide-react";
import fixture from "@/lib/demo-traces.json";

type DemoRun = (typeof fixture.runs)[number];
type DemoFinding = (typeof fixture.findings)[number];

const investigations: Record<string, { title: string; observation: string; cause: string; fix: string; verify: string; contract: string }> = {
  competitor_evidence: {
    title: "Unsupported company claims",
    observation: "The completed report describes Acme's business and customer. The mocked research basis cites the product field, while several other factual fields have no source URL.",
    cause: "The report accepts populated profile fields without requiring a citation for each claim. This is a hypothesis based on the returned report and basis.",
    fix: "Gate each factual report field on its own source URL. Mark unsupported fields unknown and request targeted research before publishing them.",
    verify: "Replay the Acme fixture. Check that every factual profile field has a matching citation or is explicitly unknown, then rerun competitor_evidence_check.",
    contract: "Every published competitor claim has field-level evidence",
  },
  no_recovery: {
    title: "Parallel failure stops the agent",
    observation: "The first profile_site call raises “Parallel research failed.” The root run ends with an error and no later tool span or fallback report appears.",
    cause: "The profile step lets the Parallel exception terminate the graph. No bounded retry or incomplete-result path is visible in this trace.",
    fix: "Catch the transient task error, retry within a limit, and return an explicit incomplete report if the service stays unavailable.",
    verify: "Replay the failing Parallel fixture. Confirm that a retry or fallback is traced and that the agent never reports success without a completed profile.",
    contract: "A failed research task produces a bounded recovery or an explicit incomplete result",
  },
};

function time(value: string) {
  return `${new Date(value).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function DemoTraceWorkspace({ view }: { view: "overview" | "investigation" }) {
  const [selectedId, setSelectedId] = useState(fixture.runs.find((run) => run.status === "error")?.trace_id || fixture.runs[0].trace_id);
  const [copied, setCopied] = useState(false);
  const selectedRun: DemoRun = fixture.runs.find((run) => run.trace_id === selectedId) || fixture.runs[0];
  const finding: DemoFinding = fixture.findings.find((item) => item.trace_id === selectedRun.trace_id)!;
  const investigation = investigations[finding.check];

  async function copyHandoff() {
    const handoff = [
      "Spectre investigation (local test fixture)",
      `Trace: ${selectedRun.trace_id}`,
      `Check: ${finding.check}`,
      `Observed: ${investigation.observation}`,
      `Likely cause (hypothesis): ${investigation.cause}`,
      `Suggested fix: ${investigation.fix}`,
      `Verify: ${investigation.verify}`,
    ].join("\n");
    await navigator.clipboard.writeText(handoff);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return <main>
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="mono flex items-center gap-2 text-[10px] uppercase tracking-[.18em] text-blue-700"><FlaskConical size={14} /> Saved test traces</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-[-.055em]">{view === "investigation" ? "Investigate the break" : "Agents and evidence"}</h1>
        <p className="mt-3 max-w-2xl text-slate-500">Two competitor research runs are preloaded from the repository&apos;s deterministic tests. Select a run to inspect its steps and investigation.</p>
      </div>
      <Link href={view === "investigation" ? "/app" : "/app/investigation"} className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium">{view === "investigation" ? "Trace overview" : "Open investigation"}<ArrowRight size={14} /></Link>
    </div>

    <div className="mt-6 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4 text-sm leading-6 text-blue-950">
      <strong>Trace source.</strong> These are snapshots of local FakeParallel test runs, not live NeatLogs records. The probe cases are prepared examples; GEPA optimization is not running in this view.
    </div>

    <div className="mt-6 grid gap-4 sm:grid-cols-3">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 card-shadow"><p className="text-xs text-slate-500">Traces loaded</p><p className="mt-2 text-3xl font-semibold">{fixture.runs.length}</p><p className="mt-1 text-xs text-slate-500">Local test snapshots</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 card-shadow"><p className="text-xs text-slate-500">Checks flagged</p><p className="mt-2 text-3xl font-semibold">{fixture.raw_finding_count}</p><p className="mt-1 text-xs text-slate-500">2 representative findings below</p></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5 card-shadow"><p className="text-xs text-slate-500">Prepared probe cases</p><p className="mt-2 text-3xl font-semibold">{fixture.runs.length}</p><p className="mt-1 text-xs text-slate-500">Citation gap · task failure</p></div>
    </div>

    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
      <div className="flex items-center gap-2"><ScanSearch size={18} /><h2 className="font-semibold">Break the agent · prepared probes</h2></div>
      <p className="mt-2 text-sm text-slate-500">A source check catches unsupported claims in the completed run. A forced Parallel task error exposes the missing recovery path.</p>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {fixture.runs.map((run, index) => {
          const active = run.trace_id === selectedId;
          const runFinding = fixture.findings.find((item) => item.trace_id === run.trace_id)!;
          return <button key={run.trace_id} type="button" aria-pressed={active} onClick={() => setSelectedId(run.trace_id)} className={`rounded-xl border p-4 text-left transition ${active ? "border-blue-400 bg-blue-50 ring-2 ring-blue-100" : "border-slate-200 hover:border-blue-200 hover:bg-slate-50"}`}>
            <span className="flex items-center justify-between gap-3"><span className="mono text-[10px] uppercase tracking-widest text-slate-500">Probe 0{index + 1} · {runFinding.check}</span><span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase ${run.status === "error" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"}`}>{run.status === "error" ? "Run failed" : "Contract finding"}</span></span>
            <span className="mt-3 block text-base font-semibold">{run.scenario}</span>
            <span className="mt-2 block text-sm leading-6 text-slate-600">{run.summary}</span>
            <span className="mono mt-3 block truncate text-xs text-slate-400">{run.trace_id}</span>
          </button>;
        })}
      </div>
    </section>

    <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(350px,0.85fr)]">
      <section id="trace-steps" className="min-w-0 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="mono text-[10px] uppercase tracking-widest text-blue-700">Observed trace</p><h2 className="mt-1 text-xl font-semibold">{selectedRun.scenario}</h2></div><span className={`rounded-full px-3 py-1 text-xs font-medium ${selectedRun.status === "error" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>{selectedRun.status}</span></div>
        <p className="mt-2 text-sm text-slate-600">{selectedRun.summary}</p>
        <dl className="mt-5 grid gap-3 rounded-xl bg-slate-50 p-4 text-xs sm:grid-cols-2"><div><dt className="text-slate-500">Trace ID</dt><dd className="mono mt-1 break-all text-slate-800">{selectedRun.trace_id}</dd></div><div><dt className="text-slate-500">Captured</dt><dd className="mt-1 text-slate-800">{time(selectedRun.started_at)}</dd></div><div><dt className="text-slate-500">Input</dt><dd className="mt-1 text-slate-800">{selectedRun.input}</dd></div><div><dt className="text-slate-500">Source</dt><dd className="mt-1 text-slate-800">{selectedRun.source}</dd></div></dl>
        <h3 className="mt-6 text-sm font-semibold">Execution steps</h3>
        <ol className="mt-3 space-y-3">{selectedRun.spans.map((span, index) => <li key={span.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start gap-3"><span className={`grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${span.status === "error" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"}`}>{index + 1}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{span.name}</span><span className={`text-xs ${span.status === "error" ? "text-red-700" : "text-slate-500"}`}>{span.kind} · {span.status}</span></div>{span.error && <p className="mt-2 text-sm text-red-700">{span.error}</p>}<details className="mt-2 text-xs text-slate-500"><summary className="cursor-pointer text-blue-700">Inspect input and output</summary><p className="mt-2 font-medium text-slate-600">Input</p><pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-2">{span.input}</pre><p className="mt-2 font-medium text-slate-600">Output</p><pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-2">{span.output}</pre></details></div></div></li>)}</ol>
      </section>

      <aside aria-label="Investigation pane" className="rounded-2xl border border-slate-200 bg-white p-6 card-shadow xl:sticky xl:top-24">
        <div className="flex items-start justify-between gap-3"><div><p className="mono text-[10px] uppercase tracking-widest text-blue-700">Investigation pane</p><h2 className="mt-1 text-xl font-semibold">{investigation.title}</h2></div><span className={`rounded-full px-2 py-1 text-xs font-medium ${finding.severity === "high" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"}`}>{finding.severity}</span></div>
        <p className="mono mt-3 break-all text-xs text-slate-400">{finding.check} · {finding.id}</p>
        <div className="mt-5 space-y-5 text-sm leading-6"><div><h3 className="font-semibold">Contract being checked</h3><p className="mt-1 text-slate-600">{investigation.contract}</p></div><div><h3 className="font-semibold">Observed evidence</h3><p className="mt-1 text-slate-600">{investigation.observation}</p><p className="mono mt-2 break-all text-xs text-slate-400">Trace {finding.trace_id} · span {finding.span_id}</p></div><div><h3 className="font-semibold">Likely cause · hypothesis</h3><p className="mt-1 text-slate-600">{investigation.cause}</p></div><div><h3 className="font-semibold">Suggested fix</h3><p className="mt-1 text-slate-600">{investigation.fix}</p></div><div><h3 className="font-semibold">How to verify</h3><p className="mt-1 text-slate-600">{investigation.verify}</p></div></div>
        <button type="button" onClick={() => void copyHandoff()} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700">{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? "Copied investigation" : "Copy investigation"}</button>
        <p className="mt-3 text-xs text-slate-500">Suggested changes are untested. This pane reads the saved fixture and does not change agent code.</p>
      </aside>
    </div>
  </main>;
}
