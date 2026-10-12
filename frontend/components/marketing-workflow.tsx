"use client";

import { useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Check, Code2, GitBranch, ScanSearch, TriangleAlert } from "lucide-react";

const steps = [
  { name: "Connect", title: "Start with the agent you already built.", copy: "Wrap your agent and tools with the Spectre SDK. Keep the inputs, tool calls, outputs, and errors together as one trace." },
  { name: "Challenge", title: "GEPA puts on the red hat.", copy: "Transform a starting query into new prompts. Use feedback from each run to search for inputs that expose the agent’s limits." },
  { name: "Observe", title: "Every failure leaves a trail.", copy: "NeatLogs captures the execution path. Follow the exact tool call or response where the agent departed from its task." },
  { name: "Investigate", title: "Theo picks up where the trace ends.", copy: "Bring the failing trace and repository context into an investigation. Get a likely cause, a suggested change, and a way to verify it." },
];

function ConnectView() {
  return <div className="grid gap-6 p-6 md:grid-cols-[1.15fr_1fr] md:p-9">
    <div><p className="mono text-[10px] uppercase tracking-widest text-blue-300">Your Python agent</p><h3 className="mt-3 text-2xl font-medium">A small wrapper.<br />The full execution path.</h3><pre className="mono mt-6 overflow-x-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-7 text-blue-200">{`import healer\n\nhealer.init(workflow_name="research")\n\n@healer.agent\ndef run_agent(prompt):\n    return your_agent(prompt)`}</pre></div>
    <div className="flex flex-col justify-center gap-3">{[[Code2, "Agent entry point", "The request that starts the run"], [GitBranch, "Tools and decisions", "The steps between request and response"], [ScanSearch, "Trace evidence", "Inputs, outputs, and errors in context"]].map(([Icon, title, copy]) => { const I = Icon as typeof Code2; return <div key={String(title)} className="rounded-2xl border border-white/10 bg-white/5 p-4"><I size={18} className="text-blue-300" /><p className="mt-3 text-sm font-medium">{String(title)}</p><p className="mt-1 text-xs leading-5 text-white/50">{String(copy)}</p></div>; })}</div>
  </div>;
}

function ChallengeView() {
  return <div className="p-6 md:p-9">
    <p className="mono text-[10px] uppercase tracking-widest text-blue-300">Adversarial prompt search</p><h3 className="mt-3 text-2xl font-medium">One query. More ways to break.</h3>
    <div className="mt-7 grid items-center gap-5 sm:grid-cols-[130px_1fr]">
      <div className="mx-auto grid size-28 place-items-center rounded-full border border-blue-400/60 bg-blue-500/10 text-center"><div><p className="text-xl font-semibold text-blue-200">GEPA</p><p className="mt-1 text-[10px] text-white/50">Evolve the prompt</p></div></div>
      <div className="relative space-y-3 sm:border-l sm:border-white/15 sm:pl-7">{[
        ["Clear request", "Within contract", false], ["Ambiguous intent", "Within contract", false], ["Pressure to skip verification", "Contract failure", true], ["Conflicting instructions", "Within contract", false],
      ].map(([label, status, failed]) => <div key={String(label)} className={`relative flex flex-wrap items-center justify-between gap-2 rounded-xl border px-4 py-3 ${failed ? "border-red-400/40 bg-red-400/10" : "border-white/10 bg-white/5"}`}><span className="absolute -left-7 hidden h-px w-7 bg-white/15 sm:block" /><span className="text-sm">{label}</span><span className={`flex items-center gap-1.5 text-[10px] ${failed ? "text-red-300" : "text-emerald-300"}`}>{failed ? <TriangleAlert size={12} /> : <Check size={12} />}{status}</span></div>)}</div>
    </div>
    <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-white/10 pt-4 text-xs text-white/60"><span>Failure feedback</span><ArrowRight size={12} /><span>Next prompt</span><ArrowRight size={12} /><span>Another measured run</span></div>
  </div>;
}

function ObserveView() {
  return <div className="p-6 md:p-9"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="mono text-[10px] uppercase tracking-widest text-blue-300">NeatLogs · execution trace</p><h3 className="mt-3 text-2xl font-medium">The answer says success.<br />The trace says otherwise.</h3></div><span className="rounded-full bg-red-400/10 px-3 py-1 text-xs text-red-300">Finding to investigate</span></div>
    <ol className="mt-7 space-y-3">{[["01", "agent.run", "Request received", false], ["02", "lookup_order", "Order found", false], ["03", "confirm_payment", "Tool returned a timeout", true], ["04", "final_response", "“Your order is confirmed.”", true]].map(([number, name, result, failed]) => <li key={String(number)} className={`grid gap-2 rounded-xl border p-4 sm:grid-cols-[26px_1fr_1fr] ${failed ? "border-red-400/25 bg-red-400/5" : "border-white/10 bg-white/5"}`}><span className="mono text-xs text-white/35">{number}</span><span className="mono text-xs">{name}</span><span className={`text-xs ${failed ? "text-red-300" : "text-white/50"}`}>{result}</span></li>)}</ol>
    <p className="mt-5 text-xs leading-6 text-white/50">A completed run can still violate its task. Inspect the observed steps alongside the final response.</p>
  </div>;
}

function InvestigateView() {
  return <div className="grid gap-5 p-6 md:grid-cols-[1fr_1.05fr] md:p-9"><div><p className="mono text-[10px] uppercase tracking-widest text-blue-300">Theo · investigation</p><h3 className="mt-3 text-2xl font-medium">From a broken run<br />to a useful next step.</h3><div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-xs font-medium text-blue-200">Evidence</p><p className="mt-2 text-sm leading-6 text-white/65">Payment confirmation timed out. The agent then told the user their order was confirmed.</p><p className="mono mt-4 text-[10px] text-white/35">Trace → tool result → response</p></div></div><div className="space-y-3">{[["Likely cause", "The success path may not require a confirmed payment result."], ["Suggested change", "Require confirmation before reporting success. Handle the timeout explicitly."], ["Verify", "Replay the timeout. Check the answer and ensure no duplicate charge."]].map(([title, copy]) => <div key={title} className="rounded-2xl border border-white/10 bg-black/20 p-4"><p className="text-xs font-semibold text-blue-200">{title}</p><p className="mt-2 text-xs leading-6 text-white/60">{copy}</p></div>)}</div></div>;
}

const views = [ConnectView, ChallengeView, ObserveView, InvestigateView];

export function ProductWalkthrough() {
  const [active, setActive] = useState(1);
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  const View = views[active];
  return <section id="loop" className="theme-dark relative overflow-hidden bg-[#0c0c0c] px-5 py-24 text-white md:px-9 md:py-32">
    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(37,99,235,.15),transparent_65%)]" />
    <div className="relative mx-auto max-w-[1320px]">
      <p className="mono text-[10px] uppercase tracking-[.2em] text-blue-300">The Spectre workflow</p>
      <h2 className="mt-5 max-w-4xl text-4xl font-semibold tracking-[-.055em] md:text-6xl">Put your agent under pressure.<br /><span className="text-white/40">Follow the failure to a fix.</span></h2>
      <div className="mt-12 grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-12">
        <div role="tablist" aria-label="Spectre workflow" className="grid grid-cols-2 gap-2 lg:flex lg:flex-col">{steps.map((step, index) => <button type="button" role="tab" aria-selected={active === index} tabIndex={active === index ? 0 : -1} ref={(node) => { tabs.current[index] = node; }} onKeyDown={(event) => {
          const next = event.key === "Home" ? 0 : event.key === "End" ? steps.length - 1 : ["ArrowRight", "ArrowDown"].includes(event.key) ? (index + 1) % steps.length : ["ArrowLeft", "ArrowUp"].includes(event.key) ? (index + steps.length - 1) % steps.length : null;
          if (next !== null) { event.preventDefault(); setActive(next); tabs.current[next]?.focus(); }
        }} aria-controls="workflow-panel" id={`workflow-tab-${index}`} key={step.name} onClick={() => setActive(index)} className={`rounded-2xl border p-4 text-left transition lg:p-5 ${active === index ? "border-blue-400/50 bg-blue-500/10" : "border-white/10 hover:bg-white/5"}`}><span className="mono text-[10px] text-white/40">0{index + 1}</span><span className="ml-3 text-sm font-medium">{step.name}</span><span className={`mt-3 hidden text-xs leading-6 lg:block ${active === index ? "text-white/65" : "text-white/35"}`}>{step.copy}</span></button>)}</div>
        <div className="min-w-0"><div className="overflow-hidden rounded-3xl border border-white/15 bg-[#141820] shadow-2xl"><div className="flex items-center justify-between border-b border-white/10 px-5 py-4"><span className="mono text-[10px] text-white/40">spectre / {steps[active].name.toLowerCase()}</span><span className="text-[10px] text-white/40">Workflow example</span></div><div id="workflow-panel" role="tabpanel" aria-labelledby={`workflow-tab-${active}`}><AnimatePresence mode="wait"><motion.div key={active} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}><View /></motion.div></AnimatePresence></div></div><h3 className="mt-6 text-xl font-medium">{steps[active].title}</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-white/50 lg:hidden">{steps[active].copy}</p></div>
      </div>
    </div>
  </section>;
}
