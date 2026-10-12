import Image from "next/image";
import { ArrowRight, FileText, GitPullRequest, Play, ScanSearch, ShieldCheck, Terminal, TriangleAlert } from "lucide-react";
import { CopyCodeButton } from "./copy-code-button";
import { Logo } from "./logo";
import { ProductWalkthrough } from "./marketing-workflow";

const workspaceHref = "/login";
const sdkSnippet = `import healer

healer.init(workflow_name="my-agent")

@healer.agent
def run_agent(prompt):
    return your_existing_agent(prompt)

with healer.session("my-agent", "session-001"):
    result = run_agent("Your user's request")`;

const birds = [
  { top: "12%", size: 40 },
  { top: "22%", size: 26 },
  { top: "7%", size: 32 },
  { top: "29%", size: 20 },
];

const birdUp = "M1 7 Q6.5 -1 12 6 Q17.5 -1 23 7";

function Birds() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 z-[2] h-[45%] text-ink">
      {birds.map((bird, index) => (
        <div
          key={index}
          className={`hero-bird hero-bird-${index + 1} absolute left-0`}
          style={{ top: bird.top }}
        >
          <div className="hero-bird-bob">
            <svg width={bird.size} height={bird.size / 2} viewBox="0 0 24 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d={birdUp} />
            </svg>
          </div>
        </div>
      ))}
    </div>
  );
}

function Hero() {
  return (
    <section className="relative min-h-[760px] h-svh bg-neutral-100">
      <div className="sticky top-0 h-svh overflow-hidden bg-blue-50">
        <Image
          src="/images/spectre-river-fantasy.png"
          alt=""
          aria-hidden
          fill
          sizes="100vw"
          quality={70}
          loading="eager"
          fetchPriority="high"
          className="hero-scenic object-cover object-[center_54%]"
        />
        <Birds />
        <div className="absolute inset-0 z-[3] bg-[linear-gradient(180deg,rgba(239,246,255,.96)_0%,rgba(239,246,255,.76)_42%,rgba(219,234,254,.18)_76%,rgba(10,10,10,.1)_100%)]" />
        <div className="hero-grain absolute inset-0 z-[4] opacity-15" />

        <div className="relative z-10 mx-auto flex h-full max-w-[1480px] flex-col px-5 pb-12 pt-32 md:px-9">
          <div className="mx-auto max-w-6xl text-center">
            <h1 className="display text-[clamp(3.25rem,8.5vw,8rem)] font-semibold text-ink">
              <span className="block text-neutral-800">Find the <span className="text-blue-600">ghosts</span><br />in your agents.</span>
            </h1>
            <p className="mx-auto mt-7 max-w-2xl text-base leading-7 text-neutral-700 md:text-lg">Before your users do. Spectre challenges your agent with GEPA, follows the failures through NeatLogs, and brings in Theo to help you fix them.</p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <a href={workspaceHref} className="flex min-h-12 items-center gap-2 rounded-full border border-blue-200 bg-white/90 px-6 text-sm font-medium text-neutral-950 backdrop-blur transition-colors hover:border-blue-500 hover:bg-blue-50">Explore the workspace <ArrowRight size={16} /></a>
              <a href="#loop" className="flex min-h-12 items-center gap-2 px-5 text-sm font-medium text-neutral-700 hover:text-blue-700"><Play size={15} /> See how it works</a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SdkSection() {
  return <section id="sdk" className="mx-auto grid max-w-[1320px] gap-12 px-5 py-24 md:px-9 md:py-32 lg:grid-cols-[.9fr_1.1fr] lg:items-center">
    <div><p className="mono text-[10px] uppercase tracking-[.2em] text-blue-700">The Python SDK</p><h2 className="mt-5 text-4xl font-semibold tracking-[-.055em] md:text-6xl">Your agent.<br /><span className="text-neutral-600">A few lines closer.</span></h2><p className="mt-6 max-w-lg text-base leading-7 text-neutral-600">Wrap your existing entry point with <code className="text-sm text-blue-700">@healer.agent</code>. Add <code className="text-sm text-blue-700">@healer.tool</code> to the tools you want to inspect. Spectre records what happens between the request and the response.</p><p className="mt-4 max-w-lg text-sm leading-6 text-neutral-600">Set your NeatLogs ingest key to export traces, or keep them locally while developing. Your agent logic stays yours.</p><a href={workspaceHref} className="mt-7 inline-flex items-center gap-2 text-sm font-medium text-blue-700">Open the workspace <ArrowRight size={15} /></a></div>
    <div className="overflow-hidden rounded-3xl border border-neutral-800 bg-[#11151c] shadow-xl"><div className="flex items-center justify-between border-b border-white/10 px-5 py-4"><span className="mono flex items-center gap-2 text-xs text-white/60"><Terminal size={14} /> agent.py</span><CopyCodeButton code={sdkSnippet} /></div><pre className="mono overflow-x-auto p-5 text-xs leading-7 text-blue-100 md:p-7 md:text-sm"><code>{sdkSnippet}</code></pre><p className="border-t border-white/10 px-5 py-4 text-xs text-white/60">Replace your_existing_agent with your existing function or graph entry point.</p></div>
  </section>;
}

export function MarketingHome() {
  return <main className="bg-neutral-100 text-ink">
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-3 pt-3 md:px-6 md:pt-4">
      <div className="nav-blur pointer-events-auto mx-auto flex h-[62px] max-w-[1480px] items-center justify-between rounded-2xl border border-white/70 px-4 shadow-[0_14px_45px_rgba(10,10,10,.08)] ring-1 ring-neutral-200/80 md:px-5"><Logo /><nav aria-label="Main navigation" className="hidden items-center gap-7 text-sm text-neutral-600 md:flex"><a href="#loop" className="hover:text-blue-700">How it works</a><a href="#theo" className="hover:text-blue-700">Meet Theo</a><a href="#sdk" className="hover:text-blue-700">SDK</a></nav><a href={workspaceHref} className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700">Open app <ArrowRight size={15} /></a></div>
    </header>

    <Hero />

    <section className="mx-auto max-w-[1320px] px-5 py-24 md:px-9 md:py-32">
      <div className="grid gap-8 lg:grid-cols-2 lg:items-end"><div><p className="mono text-[10px] uppercase tracking-[.2em] text-blue-700">The bugs beyond the happy path</p><h2 className="mt-5 text-4xl font-semibold tracking-[-.055em] md:text-6xl">It worked in testing.<br /><span className="text-neutral-600">Then a user tried it.</span></h2></div><p className="max-w-xl text-lg leading-8 text-neutral-600">A different question. A tool that fails. A response that quietly drifts from the task. Spectre is built to surface these ghost issues before they become your next production incident.</p></div>
      <div className="mt-12 grid gap-4 md:grid-cols-3">{[["01", "A question you didn’t test", "GEPA varies the query and uses feedback to find where the agent’s behavior starts to break."], ["02", "A failure hidden in the trace", "A successful return value can hide a failed tool call or an unsupported answer. Inspect the steps behind it."], ["03", "A bug without a next step", "Theo connects the evidence to a likely cause and a fix you can take back to your code."]].map(([number, title, copy]) => <article key={number} className="rounded-3xl border border-neutral-200 bg-white p-6"><span className="mono text-xs text-blue-600">{number}</span><h3 className="mt-8 text-xl font-medium tracking-tight">{title}</h3><p className="mt-3 text-sm leading-6 text-neutral-500">{copy}</p></article>)}</div>
    </section>

    <ProductWalkthrough />

    <section id="theo" className="mx-auto max-w-[1320px] px-5 py-24 md:px-9 md:py-32">
      <div className="grid gap-8 lg:grid-cols-2 lg:items-end"><div><p className="mono text-[10px] uppercase tracking-[.2em] text-blue-700">Meet Theo · the investigation agent</p><h2 className="mt-5 text-4xl font-semibold tracking-[-.055em] md:text-6xl">The red team finds it.<br /><span className="text-neutral-600">Theo follows it through.</span></h2></div><p className="max-w-xl text-lg leading-8 text-neutral-600">Once a request or response fails, Theo follows the NeatLogs trace and relevant repository context. The investigation turns an unexplained failure into evidence, a suggested fix, and a replay plan.</p></div>
      <div className="mt-12 overflow-hidden rounded-3xl border border-neutral-200 bg-white shadow-[0_20px_70px_rgba(0,0,0,.05)] lg:grid lg:grid-cols-[.85fr_1.15fr]">
        <div className="border-b border-neutral-200 p-6 md:p-9 lg:border-b-0 lg:border-r"><span className="flex items-center gap-2 text-xs font-medium text-red-700"><TriangleAlert size={15} /> Failure found</span><h3 className="mt-5 text-2xl font-medium tracking-tight">A research task fails.<br />The agent has no recovery.</h3><div className="mono mt-7 space-y-3 rounded-2xl bg-neutral-50 p-4 text-xs"><p className="text-neutral-500">agent.run</p><p className="pl-3 text-neutral-600">↳ profile_site</p><p className="pl-6 text-red-700">Parallel research failed</p><p className="border-t border-neutral-200 pt-3 text-neutral-500">No fallback report returned</p></div><p className="mt-5 text-sm leading-6 text-neutral-500">A concrete failure from the competitor research workflow. Each suggested change starts with what the run actually recorded.</p></div>
        <div className="grid-paper p-6 md:p-9"><div className="rounded-2xl bg-[#11151c] p-5 text-white"><p className="flex items-center gap-2 text-xs text-blue-200"><ScanSearch size={15} /> Theo’s investigation</p><h3 className="mt-4 text-lg font-medium">The profile exception may terminate the graph.</h3><p className="mt-3 text-sm leading-6 text-white/50">The failed tool call is followed by an error at the root. No successful retry or fallback appears in the trace.</p></div><div className="mt-4 grid gap-4 sm:grid-cols-2"><div className="rounded-2xl border border-neutral-200 bg-white p-5"><p className="text-sm font-semibold">Suggested change</p><p className="mt-3 text-xs leading-6 text-neutral-500">Add a bounded retry, then return an explicit incomplete report if research remains unavailable.</p></div><div className="rounded-2xl border border-neutral-200 bg-white p-5"><p className="text-sm font-semibold">Verification plan</p><p className="mt-3 text-xs leading-6 text-neutral-500">Replay the failed response. Confirm recovery is traced and the agent does not invent a result.</p></div></div></div>
      </div>
      <div className="mt-6 grid gap-5 md:grid-cols-2"><article className="rounded-3xl border border-blue-200 bg-blue-50 p-6 md:p-8"><FileText size={22} className="text-blue-700" /><p className="mono mt-6 text-[10px] uppercase tracking-widest text-blue-700">Take the investigation to your code</p><h3 className="mt-3 text-2xl font-medium tracking-tight">A handoff for your coding agent.</h3><p className="mt-3 text-sm leading-7 text-neutral-600">Copy the evidence, likely cause, suggested fix, and verification steps into your coding agent. Keep the trace attached to the work.</p><a href={workspaceHref} className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-blue-700">Explore an investigation <ArrowRight size={15} /></a></article><article className="rounded-3xl border border-neutral-200 bg-white p-6 md:p-8"><div className="flex items-center justify-between"><GitPullRequest size={22} className="text-neutral-600" /><span className="rounded-full bg-neutral-100 px-3 py-1 text-[10px] font-medium text-neutral-600">In development</span></div><p className="mono mt-6 text-[10px] uppercase tracking-widest text-neutral-500">Where we’re taking Theo</p><h3 className="mt-3 text-2xl font-medium tracking-tight">A tested PR for your team to review.</h3><p className="mt-3 text-sm leading-7 text-neutral-600">Connect GitHub, let Theo work in a sandbox, run the tests, and bring the proposed fix back as a pull request. Your team reviews, gives feedback, and approves.</p><p className="mt-6 flex items-center gap-2 text-xs text-neutral-500"><ShieldCheck size={14} /> Human review stays part of the loop.</p></article></div>
    </section>

    <SdkSection />

    <div className="theme-dark bg-[#0c0c0c] p-3 md:p-6"><footer className="theme-dark relative overflow-hidden rounded-3xl bg-[#1d4ed8] text-ink"><div aria-hidden className="footer-aurora absolute inset-0 opacity-90" /><div className="relative mx-auto max-w-[1320px] px-5 py-12 md:px-9 md:py-16"><div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end"><div><p className="mono text-[10px] uppercase tracking-[.2em] text-white/70">Build it. Then breathe.</p><h2 className="mt-5 max-w-3xl text-4xl font-semibold tracking-[-.055em] text-white md:text-6xl">Ship your agent.<br />Keep your peace.</h2></div><div className="max-w-sm"><p className="text-sm leading-7 text-white/80">Challenge the behavior. Understand the failure. Give your team a clear path to the fix.</p><a href={workspaceHref} className="mt-6 inline-flex h-12 items-center gap-2 rounded-full bg-white px-6 text-sm font-medium text-neutral-950 transition hover:-translate-y-0.5 hover:bg-blue-50">Open the workspace <ArrowRight size={16} /></a></div></div><div className="mt-12 flex flex-wrap items-center justify-between gap-5 border-t border-white/20 pt-6 text-xs text-white/70"><span>© 2026 Spectre</span><nav aria-label="Footer navigation" className="flex gap-6"><a href="#loop" className="hover:text-white">The workflow</a><a href="#theo" className="hover:text-white">Meet Theo</a><a href="#sdk" className="hover:text-white">SDK</a></nav><span>Built to find the ghosts before your users do.</span></div></div></footer></div>
  </main>;
}
