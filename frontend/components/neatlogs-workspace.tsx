"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CircleHelp, Copy, RefreshCw, ScanSearch, X } from "lucide-react";
import { InvestigationPanel } from "@/components/investigation-panel";
import { ObservedRuns, type ObservedRun } from "@/components/observed-runs";

type Project = { project_id: string; name: string; role: string };
type Agent = { project_id: string; workflow_name: string };
type Connection = { connected: boolean; host: string; projects: Project[]; agents: Agent[] };
type Finding = { finding: { id: string; reason: string; severity: string; trace_id: string; trace_url: string | null };
  session_id: string; suggestion: string; invocation_path: string[]; copy_to_agent: string };
type Report = { trace_count: number; finding_count: number; rows: Finding[]; runs: ObservedRun[] };

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, cache: "no-store" });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}

export function NeatlogsWorkspace() {
  const [account, setAccount] = useState<Connection | null>(null);
  const [projectId, setProjectId] = useState("");
  const [workflowName, setWorkflowName] = useState("");
  const [workflows, setWorkflows] = useState<string[]>([]);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [readToken, setReadToken] = useState("");
  const [host, setHost] = useState("https://app.neatlogs.com");
  const [report, setReport] = useState<Report | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const loadAccount = useCallback(async () => {
    const data = await request<Connection>("/api/neatlogs");
    setAccount(data); setHost(data.host);
    setProjectId((current) => data.projects.some((item) => item.project_id === current) ? current : "");
  }, []);
  useEffect(() => { void loadAccount().catch((cause) => setError(cause.message)); }, [loadAccount]);
  useEffect(() => {
    if (!helpOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setHelpOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [helpOpen]);
  useEffect(() => {
    if (!projectId) { setWorkflows([]); setWorkflowName(""); return; }
    let active = true;
    setWorkflows([]); setWorkflowName(""); setReport(null); setWorkflowLoading(true);
    request<{ workflows: string[] }>(`/api/neatlogs/workflows?project_id=${encodeURIComponent(projectId)}`)
      .then((value) => { if (active) { setWorkflows(value.workflows); setError("");
        const saved = account?.agents.find((agent) => agent.project_id === projectId && value.workflows.includes(agent.workflow_name));
        if (saved) setWorkflowName(saved.workflow_name);
      } })
      .catch((cause) => { if (active) setError(cause.message); })
      .finally(() => { if (active) setWorkflowLoading(false); });
    return () => { active = false; };
  }, [projectId]);
  useEffect(() => {
    if (!projectId || !workflowName) { setReport(null); return; }
    let active = true;
    setLoading(true);
    request<Report>(`/api/neatlogs/report?project_id=${encodeURIComponent(projectId)}&workflow_name=${encodeURIComponent(workflowName)}`)
      .then((value) => { if (active) { setReport(value); setError(""); } })
      .catch((cause) => { if (active) { setReport(null); setError(cause.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, workflowName, refresh]);

  async function connect(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await request("/api/neatlogs", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read_token: readToken || undefined, host }) });
      setReadToken(""); await loadAccount(); setRefresh((value) => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not connect NeatLogs"); }
    finally { setBusy(false); }
  }

  async function chooseAgent(name: string) {
    setError(""); setReport(null);
    if (!name) { setWorkflowName(""); return; }
    setBusy(true);
    try {
      await request("/api/neatlogs/agents", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, workflow_name: name }) });
      setWorkflowName(name); await loadAccount();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not select agent"); }
    finally { setBusy(false); }
  }

  const projectName = account?.projects.find((item) => item.project_id === projectId)?.name || "";
  const handoff = report ? `Spectre trace investigation\nNeatLogs project: ${projectName}\nAgent: ${workflowName}\nObserved traces: ${report.trace_count}\nFindings: ${report.finding_count}\n\n${report.rows.map((row) => row.copy_to_agent).join("\n\n") || "No findings in the synced traces."}` : "";

  return <main>
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="mono text-[10px] uppercase tracking-[.18em] text-blue-700">NeatLogs ingestion</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-[-.055em]">Agents and evidence</h1>
        <p className="mt-3 text-slate-500">Connect NeatLogs, choose a project, then choose an agent found in its traces.</p></div>
      <button type="button" onClick={() => { void loadAccount(); setRefresh((value) => value + 1); }} className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm"><RefreshCw size={14} />Refresh</button>
    </div>
    {error && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}{error.toLowerCase().includes("token") && account?.connected && " Enter a replacement read token below to reconnect."}</p>}
    <section id="neatlogs" className="mt-7 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">NeatLogs connection</h2><p className="mt-1 text-sm text-slate-500">{account?.connected ? "Your read token is saved. Refresh projects or replace the token here." : "Enter a service-account read token to discover your projects."}</p></div>
        <button type="button" onClick={() => setHelpOpen(true)} className="flex items-center gap-2 text-sm font-medium text-blue-700"><CircleHelp size={16} />How to get a read token</button></div>
      <form onSubmit={connect} className="mt-5 flex flex-wrap items-end gap-3">
        <label className="min-w-60 flex-1 text-sm font-medium">Read token<input type="password" autoComplete="off" value={readToken} onChange={(event) => setReadToken(event.target.value)} required={!account?.connected} placeholder={account?.connected ? "Saved — enter only to replace" : "Service-account token"} className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" /></label>
        <label className="text-sm font-medium">Region<select value={host} onChange={(event) => setHost(event.target.value)} className="mt-2 block rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"><option value="https://app.neatlogs.com">US</option><option value="https://eu.app.neatlogs.com">EU</option></select></label>
        <button disabled={busy} className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{busy ? "Loading…" : account?.connected ? "Refresh projects" : "Connect"}</button>
      </form>
      {account?.connected && <p className="mt-3 text-xs text-slate-500">If your token expires, mint a replacement in NeatLogs and enter it here. Saved agents remain attached to your account.</p>}
    </section>
    <section id="projects" className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
      <div className="flex items-center gap-2"><ScanSearch size={18} /><h2 className="font-semibold">Project and agent</h2></div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Project<select aria-label="Select NeatLogs project" value={projectId} onChange={(event) => setProjectId(event.target.value)} className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"><option value="">Choose a project</option>{account?.projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name}</option>)}</select></label>
        <label className="text-sm font-medium">Agent<select aria-label="Select agent" disabled={!projectId || busy || workflowLoading} value={workflowName} onChange={(event) => { void chooseAgent(event.target.value); }} className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm disabled:opacity-50"><option value="">{workflowLoading ? "Finding agents…" : "Choose an agent"}</option>{workflows.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      </div>
      {projectId && !workflowLoading && workflows.length === 0 && <p className="mt-3 text-sm text-slate-500">No agent workflows found in this project’s traces yet.</p>}
      {loading && <p className="mt-6 text-sm text-slate-500">Syncing {workflowName} traces…</p>}
      {!loading && report && <><div className="mt-5 flex flex-wrap items-center gap-4 text-sm"><span>{report.trace_count} traces</span><span>{report.finding_count} findings</span><span className="text-slate-500">Incremental sync uses the saved workflow and a trace timestamp</span><button type="button" onClick={() => { void navigator.clipboard.writeText(handoff).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800); }); }} className="ml-auto flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2"><Copy size={14} />{copied ? "Copied" : "Copy trace handoff"}</button></div>
        <div className="mt-5 divide-y divide-slate-100">{report.rows.map((row) => <article key={row.finding.id} className="py-5"><div><span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">{row.finding.severity}</span><span className="mono ml-2 text-xs text-slate-400">{row.finding.id}</span></div><p className="mt-3 text-sm font-medium">{row.finding.reason}</p><p className="mt-2 text-sm text-slate-500">Suggested check: {row.suggestion}</p><p className="mono mt-2 text-xs text-slate-400">Session {row.session_id} · Trace {row.finding.trace_id}</p>{row.invocation_path?.length > 0 && <p className="mt-2 text-xs text-slate-500">Observed path: {row.invocation_path.join(" → ")}</p>}{row.finding.trace_url && <a className="mt-2 inline-block text-sm text-blue-700" href={row.finding.trace_url} target="_blank" rel="noreferrer">View trace</a>}<InvestigationPanel projectId={projectId} workflowName={workflowName} findingId={row.finding.id} /></article>)}{report.rows.length === 0 && <p className="py-8 text-sm text-slate-500">No findings in the synced traces.</p>}</div></>}
    </section>
    {report && <ObservedRuns runs={report.runs} />}
    {helpOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setHelpOpen(false); }}><div role="dialog" aria-modal="true" aria-labelledby="neatlogs-help-title" className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><p className="mono text-[10px] uppercase tracking-widest text-blue-700">NeatLogs setup</p><h2 id="neatlogs-help-title" className="mt-2 text-2xl font-semibold">Get read access</h2></div><button type="button" autoFocus aria-label="Close setup instructions" onClick={() => setHelpOpen(false)}><X size={20} /></button></div><ol className="mt-5 list-decimal space-y-3 pl-5 text-sm leading-6 text-slate-700"><li>Sign in to <a href="https://app.neatlogs.com" target="_blank" rel="noreferrer" className="text-blue-700 underline">NeatLogs</a> with access to manage service accounts.</li><li>Open <strong>Settings → Service Accounts</strong> and create a service account for Spectre.</li><li>Bind the projects this integration should read with a suitable read-only project role.</li><li>Mint an expiring token with <code>context:read</code> and <code>observability:read</code>. Copy it once, then paste it here.</li><li>Choose a project by name, then choose an agent discovered from its trace workflow names.</li></ol><p className="mt-4 text-xs text-slate-500">When the token expires or a new project is bound, update or refresh the connection here.</p><a href="https://docs.neatlogs.com/api-reference/quickstart" target="_blank" rel="noreferrer" className="mt-5 inline-block text-sm font-medium text-blue-700 underline">Open NeatLogs API quickstart</a><div className="mt-6 text-right"><button type="button" onClick={() => setHelpOpen(false)} className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white">Done</button></div></div></div>}
  </main>;
}
