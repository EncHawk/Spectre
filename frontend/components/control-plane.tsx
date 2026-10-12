"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Copy, GitBranch, RefreshCw, ScanSearch } from "lucide-react";
import { ExampleLab } from "@/components/example-lab";
import { InvestigationPanel } from "@/components/investigation-panel";
import { ObservedRuns, type ObservedRun } from "@/components/observed-runs";
import { ProjectKeys } from "@/components/project-keys";

type Repo = { id: number; full_name: string; default_branch: string; commit_sha: string; file_count: number; indexed_at: string };
type Agent = { id: number; app_id: string; name: string; description: string; repository_id: number | null; repository_name: string | null; repository_commit: string | null };
type Finding = { finding: { id: string; reason: string; severity: string; trace_id: string; trace_url: string | null }; session_id: string; suggestion: string; candidate_locations: Array<{ file: string; line: number; url?: string }>; invocation_path?: string[]; code_neighbors?: Array<{ from: string; to: string }>; resolution: { status: string; pr_url: string | null } | null; copy_to_agent: string };
type Report = { agent: Agent; repository: { full_name: string; commit_sha: string; file_count: number; code_graph?: { node_count: number; edge_count: number } } | null; trace_count: number; finding_count: number; rows: Finding[]; runs: ObservedRun[] };

async function json<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, cache: "no-store" });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}
function post(body: unknown): RequestInit { return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }; }

export function ControlPlane() {
  const [me, setMe] = useState<{ user: { name: string; email: string }; github: string | null } | null>(null);
  const [repos, setRepos] = useState<Repo[]>([]); const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState(""); const [report, setReport] = useState<Report | null>(null);
  const [reportVersion, setReportVersion] = useState(0);
  const [repoInput, setRepoInput] = useState(""); const [appId, setAppId] = useState("");
  const [name, setName] = useState(""); const [description, setDescription] = useState("");
  const [repoId, setRepoId] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState("");
  const reload = useCallback(async () => {
    try {
      const [identity, repositoryData, agentData] = await Promise.all([
        json<{ user: { name: string; email: string }; github: string | null }>("/api/me"),
        json<{ repositories: Repo[] }>("/api/repositories"), json<{ agents: Agent[] }>("/api/agents"),
      ]);
      setMe(identity); setRepos(repositoryData.repositories); setAgents(agentData.agents);
      setSelected((current) => current || agentData.agents[0]?.app_id || "");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load workspace"); }
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  useEffect(() => {
    if (!selected) { setReport(null); return; }
    let active = true;
    json<Report>(`/api/doctor?app_id=${encodeURIComponent(selected)}`).then((value) => { if (active) { setReport(value); setError(""); } })
      .catch((cause) => { if (active) { setReport(null); setError(cause instanceof Error ? cause.message : "Diagnostics unavailable"); } });
    return () => { active = false; };
  }, [selected, reportVersion]);

  async function addRepo(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await json("/api/repositories", post({ repository: repoInput })); setRepoInput(""); await reload(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not ingest repository"); }
    finally { setBusy(false); }
  }
  async function saveAgent(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await json("/api/agents", post({ app_id: appId, name, description, repository_id: repoId || null }));
      setSelected(appId); setReportVersion((version) => version + 1); setAppId(""); setName(""); setDescription(""); await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save agent"); }
    finally { setBusy(false); }
  }
  async function copy(value: string, id: string) { await navigator.clipboard.writeText(value); setCopied(id); setTimeout(() => setCopied(""), 1800); }
  const summary = report ? `Spectre investigation handoff\nAgent: ${report.agent.name} (${report.agent.app_id})\nIntent: ${report.agent.description}\nRepository: ${report.repository?.full_name || "not connected"}\nCommit: ${report.repository?.commit_sha || "unknown"}\nObserved traces: ${report.trace_count}\nFindings: ${report.finding_count}\n\n${report.rows.map((row) => row.copy_to_agent).join("\n\n") || "No findings in this window. Confirm instrumentation and trace ingestion before drawing conclusions."}` : "";

  return <main>
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="mono text-[10px] uppercase tracking-[.18em] text-blue-700">Live workspace</p><h1 className="mt-2 text-4xl font-semibold tracking-[-.055em]">Agents and evidence</h1><p className="mt-3 text-slate-500">Connect a repository, define an agent, then inspect observed findings and copy the handoff.</p></div><button onClick={() => { void reload(); setReportVersion((version) => version + 1); }} className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm"><RefreshCw size={14} />Refresh</button></div>
    {error && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
    <div className="mt-7 grid gap-5 lg:grid-cols-2">
      <section id="repositories" className="rounded-2xl border border-slate-200 bg-white p-6 card-shadow"><div className="flex items-center gap-2"><GitBranch size={18} /><h2 className="font-semibold">GitHub repositories</h2></div><p className="mt-2 text-sm text-slate-500">{me?.github ? `Connected as ${me.github}` : "Connect GitHub to inspect repositories you can access."}</p>
        {!me?.github && <a href="/api/auth/github/start" className="mt-5 inline-flex rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white">Connect GitHub</a>}
        {me?.github && <form onSubmit={addRepo} className="mt-5 flex gap-2"><input aria-label="GitHub repository" required value={repoInput} onChange={(e) => setRepoInput(e.target.value)} placeholder="owner/repository" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm" /><button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Ingest</button></form>}
        <div className="mt-5 space-y-2">{repos.map((repo) => <div key={repo.id} className="rounded-xl bg-slate-50 p-3"><p className="font-medium">{repo.full_name}</p><p className="mono mt-1 text-xs text-slate-500">{repo.default_branch} · {repo.commit_sha.slice(0, 12)} · {repo.file_count} files</p></div>)}{repos.length === 0 && <p className="text-sm text-slate-400">No repository snapshots yet.</p>}</div>
      </section>
      <section id="agents" className="rounded-2xl border border-slate-200 bg-white p-6 card-shadow"><h2 className="font-semibold">Define agent</h2><p className="mt-2 text-sm text-slate-500">Use the same app ID as <code>healer.session(app_id, session_id)</code> in your instrumented agent.</p>
        <form onSubmit={saveAgent} className="mt-5 space-y-3"><div className="grid gap-3 sm:grid-cols-2"><input required value={appId} onChange={(e) => setAppId(e.target.value)} placeholder="app_id" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" /><input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Display name" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" /></div><textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What should this agent do?" className="min-h-20 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" /><select value={repoId} onChange={(e) => setRepoId(e.target.value)} className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"><option value="">No repository</option>{repos.map((repo) => <option key={repo.id} value={repo.id}>{repo.full_name}</option>)}</select><button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Save agent</button></form>
      </section>
    </div>
    <ProjectKeys />
    <section id="investigation" className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 card-shadow"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="flex items-center gap-2"><ScanSearch size={18} /><h2 className="font-semibold">Investigation</h2></div><p className="mt-1 text-sm text-slate-500">Follow measured traces to a likely cause, suggested fix, and a way to test it.</p></div><select aria-label="Select agent" value={selected} onChange={(e) => setSelected(e.target.value)} className="rounded-xl border border-slate-300 px-3 py-2 text-sm"><option value="">Select agent</option>{agents.map((agent) => <option key={agent.id} value={agent.app_id}>{agent.name} ({agent.app_id})</option>)}</select></div>
      {report && <><div className="mt-5 flex flex-wrap items-center gap-4 text-sm"><span>{report.trace_count} traces</span><span>{report.finding_count} findings</span><span className="text-slate-500">{report.repository?.full_name || "No repository linked"}</span>{report.repository?.code_graph && <span className="text-slate-500">{report.repository.code_graph.node_count} symbols · {report.repository.code_graph.edge_count} possible calls</span>}<button onClick={() => void copy(summary, "summary")} className="ml-auto flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2"><Copy size={14} />{copied === "summary" ? "Copied" : "Copy summary for coding agent"}</button></div>
        <div className="mt-5 divide-y divide-slate-100">{report.rows.map((row) => <article key={row.finding.id} className="py-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{row.finding.severity}</span><span className="mono ml-2 text-xs text-slate-400">{row.finding.id}</span></div><button onClick={() => void copy(row.copy_to_agent, row.finding.id)} className="flex items-center gap-2 text-sm text-blue-700">{copied === row.finding.id ? <Check size={14} /> : <Copy size={14} />}{copied === row.finding.id ? "Copied" : "Copy to agent"}</button></div><p className="mt-3 text-sm font-medium">{row.finding.reason}</p><p className="mt-2 text-sm text-slate-500">Suggested check: {row.suggestion}</p><p className="mono mt-2 text-xs text-slate-400">Session {row.session_id} · Trace {row.finding.trace_id}</p>{row.invocation_path && row.invocation_path.length > 0 && <p className="mt-2 text-xs text-slate-500">Observed path: {row.invocation_path.join(" → ")}</p>}{row.candidate_locations.length > 0 && <p className="mt-2 text-xs text-slate-500">Candidate code: {row.candidate_locations.map((location, index) => <span key={`${location.file}:${location.line}`}>{index > 0 ? ", " : ""}{location.url ? <a href={location.url} target="_blank" rel="noreferrer" className="text-blue-700">{location.file}:{location.line}</a> : `${location.file}:${location.line}`}</span>)}</p>}{row.code_neighbors && row.code_neighbors.length > 0 && <p className="mt-2 text-xs text-slate-500">Possible calls: {row.code_neighbors.slice(0, 5).map((edge) => `${edge.from} → ${edge.to}`).join("; ")}</p>}{row.finding.trace_url && <a className="mt-2 inline-block text-sm text-blue-700" href={row.finding.trace_url} target="_blank" rel="noreferrer">View trace</a>}{row.resolution && <p className="mt-2 text-xs text-slate-500">Status: {row.resolution.status}{row.resolution.pr_url && <> · <a href={row.resolution.pr_url} target="_blank" rel="noreferrer" className="text-blue-700">PR</a></>}</p>}<InvestigationPanel appId={selected} findingId={row.finding.id} /></article>)}{report.rows.length === 0 && <p className="py-8 text-sm text-slate-500">No findings in this window.</p>}</div>
      </>}{!selected && <p className="mt-6 text-sm text-slate-500">Define an agent to inspect its traces.</p>}
    </section>
    {report && <ObservedRuns runs={report.runs} />}
    <ExampleLab />
  </main>;
}
