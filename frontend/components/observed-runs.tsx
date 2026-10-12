"use client";

export type ObservedRun = {
  trace_id: string; session_id: string; name: string; status: string; source: string;
  started_at: string; trace_url: string | null; spans_truncated: boolean;
  spans: Array<{ id: string; parent_id: string | null; name: string; kind: string; status: string; input: string; output: string; error: string | null }>;
};

export function ObservedRuns({ runs }: { runs: ObservedRun[] }) {
  return <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
    <h2 className="font-semibold">Observed runs</h2>
    <p className="mt-2 text-sm text-slate-500">All returned traces for this agent, including successful runs. Span inputs and outputs are redacted and capped at 1,000 characters.</p>
    <div className="mt-4 space-y-3">{runs.map((run) => <details key={run.trace_id} className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-medium">{run.name} · {run.status} · {run.spans.length} steps · {run.session_id}</summary><p className="mono mt-2 break-all text-xs text-slate-500">Trace {run.trace_id} · {run.source} · {run.started_at}</p>{run.trace_url && <a href={run.trace_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-blue-700">Open source trace</a>}<ol className="mt-3 space-y-2">{run.spans.map((span) => <li key={span.id} className="rounded-lg bg-slate-50 p-3 text-xs"><p className="font-medium">{span.name} <span className="text-slate-500">{span.kind} · {span.status}</span></p><p className="mt-1 break-all text-slate-500">Parent: {span.parent_id || "root"}</p><p className="mt-1 break-words">Input: {span.input}</p><p className="mt-1 break-words">Output: {span.output}</p>{span.error && <p className="mt-1 text-red-700">Error: {span.error}</p>}</li>)}</ol>{run.spans_truncated && <p className="mt-2 text-xs text-slate-500">More spans exist in this trace.</p>}</details>)}{runs.length === 0 && <p className="text-sm text-slate-500">No traces returned for this agent. Instrument a run with its app ID, then refresh.</p>}</div>
  </section>;
}
