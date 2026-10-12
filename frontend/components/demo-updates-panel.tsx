"use client";

import { useEffect, useState } from "react";
import { GripVertical, X } from "lucide-react";

const cases = [
  {
    title: "Subject profile has unsupported claims",
    check: "competitor_evidence",
    status: "Needs review",
    observation: "The Acme profile contains product, customer, and problem claims. The mocked research basis cites only the product field, so the other claims have no source URL.",
    trace: ["profile_site → Parallel Task run-1", "product → acme.test/product", "what_they_do / icp / problem_solved → no citation", "report → competitor_evidence finding"],
    solutions: ["Require a source URL for each factual profile field before adding it to the report.", "Show uncited fields as unknown and queue a targeted research retry.", "Run competitor_evidence_check again and verify that every published claim has a citation."],
  },
  {
    title: "Competitor detail lacks field evidence",
    check: "competitor_evidence",
    status: "Needs review",
    observation: "Rival is kept as a competitor, but its product, customer, and problem claims have no field citations in the mocked basis. A separate revenue number is omitted because it has no source.",
    trace: ["discover_competitors → Rival and Unrelated", "enrich → Unrelated rejected; Rival accepted", "Rival why_competitor → rival.test/product", "Rival product / icp / problem_solved → no citation", "growth_metrics → sourced customers kept; unsourced revenue omitted"],
    solutions: ["Request field level research basis for every lead claim.", "Keep unsourced lead fields out of the usable report until verified.", "Preserve the current growth filter and verify omitted metrics remain absent on replay."],
  },
  {
    title: "Parallel research call fails without recovery",
    check: "no_recovery",
    status: "Run failed",
    observation: "In the tested failure case, the first Parallel Task call raises “Parallel research failed”; the graph exits without a fallback result.",
    trace: ["run → profile_site", "Parallel Task create → RuntimeError: Parallel research failed", "profile_site → failed", "run → no recovery path; no report"],
    solutions: ["Catch transient Parallel errors and retry with a bounded backoff.", "If retries fail, return an explicit incomplete report with the failed step and no invented leads.", "Replay the failing call and verify the final status reports the failure rather than success."],
  },
];

export function DemoUpdatesPanel({ onClose }: { onClose: () => void }) {
  const [width, setWidth] = useState(440);
  const [active, setActive] = useState(0);
  const [tab, setTab] = useState<"solutions" | "trace">("solutions");

  useEffect(() => {
    function onMove(event: PointerEvent) {
      if (document.body.dataset.demoResizing !== "true") return;
      setWidth(Math.max(320, Math.min(window.innerWidth - 40, window.innerWidth - event.clientX)));
    }
    function onUp() { delete document.body.dataset.demoResizing; }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => { window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp); delete document.body.dataset.demoResizing; };
  }, []);

  const item = cases[active];
  return <aside aria-label="Run updates" className="fixed inset-y-0 right-0 z-50 flex max-w-full flex-col border-l border-slate-200 bg-white shadow-2xl" style={{ width }}>
    <div onPointerDown={(event) => { event.preventDefault(); document.body.dataset.demoResizing = "true"; }} role="separator" aria-label="Resize demo panel" aria-orientation="vertical" tabIndex={0} onKeyDown={(event) => { if (event.key === "ArrowLeft") setWidth((value) => Math.min(window.innerWidth - 40, value + 24)); if (event.key === "ArrowRight") setWidth((value) => Math.max(320, value - 24)); }} className="absolute inset-y-0 left-0 z-10 flex w-3 -translate-x-1/2 cursor-col-resize items-center justify-center text-slate-400 focus:bg-blue-100"><GripVertical size={14} /></div>
    <div className="flex items-start justify-between border-b border-slate-200 p-5"><div><p className="mono text-[10px] uppercase tracking-widest text-blue-700">Tested fixture</p><h2 className="mt-1 text-xl font-semibold">Run updates</h2><p className="mt-1 text-xs text-slate-500">Competitor research agent · Acme test run</p></div><button type="button" aria-label="Close run updates" onClick={onClose} className="rounded-lg p-2 hover:bg-slate-100"><X size={18} /></button></div>
    <div className="overflow-y-auto p-5"><div className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-xs leading-5 text-blue-900">These are simulated outputs from the repository’s tested <span className="mono">plus_usage</span> agent. Trace steps summarize local test fixtures; they are not live NeatLogs records.</div>
      <div className="mt-5 space-y-2">{cases.map((entry, index) => <button key={entry.title} type="button" onClick={() => { setActive(index); setTab("solutions"); }} className={`w-full rounded-xl border p-3 text-left ${index === active ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}><span className="mono text-[10px] text-slate-500">0{index + 1} · {entry.check}</span><span className="mt-1 block text-sm font-medium">{entry.title}</span><span className="mt-1 block text-xs text-slate-500">{entry.status}</span></button>)}</div>
      <div className="mt-6 border-t border-slate-200 pt-5"><h3 className="text-base font-semibold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{item.observation}</p><div className="mt-5 flex gap-1 border-b border-slate-200">{(["solutions", "trace"] as const).map((value) => <button key={value} type="button" onClick={() => setTab(value)} className={`px-3 py-2 text-sm capitalize ${tab === value ? "border-b-2 border-blue-600 font-medium text-blue-700" : "text-slate-500"}`}>{value === "trace" ? "Trace steps" : "Possible fixes"}</button>)}</div>
      {tab === "solutions" ? <ol className="mt-4 space-y-3">{item.solutions.map((solution, index) => <li key={solution} className="flex gap-3 text-sm leading-6"><span className="mono text-blue-700">{index + 1}.</span><span>{solution}</span></li>)}</ol> : <ol className="mono mt-4 space-y-2 text-xs">{item.trace.map((step, index) => <li key={step} className={`rounded-lg p-3 ${index === item.trace.length - 1 ? "bg-amber-50 text-amber-900" : "bg-slate-50 text-slate-700"}`}>{step}</li>)}</ol>}</div>
    </div>
  </aside>;
}
