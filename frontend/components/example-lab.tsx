"use client";

import { useEffect, useState } from "react";

type Example = { id: string; title: string; steps: string[]; attack: string; cases: string[] };
type Phase = { passed: boolean; contract: string; answer: string; trace_id: string; session_id: string; checks: string[]; spans: Array<{ name: string; kind: string; status: string }> };
type Result = { example: string; title: string; attack: string; steps: string[]; before_passed: number; after_passed: number; case_count: number; provider_evidence: string; cases: Array<{ case: string; before: Phase; after: Phase }> };

export function ExampleLab() {
  const [examples, setExamples] = useState<Example[]>([]);
  const [selected, setSelected] = useState("checkout_support");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetch("/api/examples", { cache: "no-store" }).then(async (response) => {
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Could not load examples");
      setExamples(value.examples);
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load examples"));
  }, []);
  async function run() {
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch("/api/example-runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ example: selected }) });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Run failed");
      setResult(value);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Run failed"); }
    finally { setBusy(false); }
  }
  return <section id="red-team" className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><h2 className="font-semibold">LangGraph red team lab</h2><p className="mt-2 text-sm text-slate-500">Run a multi-step agent through Specter, compare flawed and repaired behavior, and inspect each observed step.</p></div><div className="flex gap-2"><select aria-label="Example agent" value={selected} onChange={(event) => { setSelected(event.target.value); setResult(null); }} className="rounded-xl border border-slate-300 px-3 py-2 text-sm">{examples.map((example) => <option key={example.id} value={example.id}>{example.title}</option>)}</select><button disabled={busy || examples.length === 0} onClick={() => void run()} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Running…" : "Run red team"}</button></div></div>
    {examples.find((example) => example.id === selected) && <p className="mt-4 text-xs text-slate-500">Flow: {examples.find((example) => example.id === selected)?.steps.join(" → ")}</p>}
    {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    {result && <><div className="mt-5 rounded-xl bg-blue-50 p-4"><p className="text-sm font-medium">Contract passes: {result.before_passed}/{result.case_count} before → {result.after_passed}/{result.case_count} after</p><p className="mt-1 text-xs text-slate-600">Attack: {result.attack}. {result.provider_evidence}.</p></div><div className="mt-4 space-y-3">{result.cases.map((row) => <details key={row.case} className="rounded-xl border border-slate-200 p-4" open={row.case !== "normal"}><summary className="cursor-pointer text-sm font-medium">{row.case}: {row.before.passed ? "pass" : "fail"} → {row.after.passed ? "pass" : "fail"}</summary><div className="mt-3 grid gap-3 md:grid-cols-2">{(["before", "after"] as const).map((phase) => { const data = row[phase]; return <div key={phase} className="rounded-lg bg-slate-50 p-3 text-xs"><p className="font-semibold uppercase tracking-wide">{phase} · {data.passed ? "contract passed" : "contract failed"}</p><p className="mt-2">{data.answer}</p><p className="mt-2 text-slate-600">Checks: {data.checks.join(", ") || "none"}</p><p className="mt-2 text-slate-600">Observed steps: {data.spans.map((span) => span.name).join(" → ")}</p><p className="mono mt-2 break-all text-slate-500">Trace {data.trace_id} · Session {data.session_id}</p></div>; })}</div><p className="mt-3 text-xs text-slate-500">Contract: {row.after.contract}</p></details>)}</div></>}
  </section>;
}
