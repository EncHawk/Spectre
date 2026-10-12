"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Copy, KeyRound } from "lucide-react";

type Project = { id: string; app_id: string; name: string };
type Key = { id: string; prefix: string; scopes: string[]; expires_at: string | null; last_used_at: string | null; revoked_at: string | null };
const allScopes = ["runs:write", "runs:read", "jobs:pull"];

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...options, cache: "no-store" });
  if (response.status === 401) { window.location.assign("/api/auth/google/start"); throw new Error("Sign in required"); }
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}

export function ProjectKeys({ onboarding = false }: { onboarding?: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState("");
  const [keys, setKeys] = useState<Key[]>([]);
  const [appId, setAppId] = useState("");
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(allScopes);
  const [revealed, setRevealed] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadProjects = useCallback(async () => {
    const data = await request<{ projects: Project[] }>("/api/projects");
    setProjects(data.projects);
    setSelected((current) => data.projects.some((project) => project.id === current) ? current : data.projects[0]?.id || "");
  }, []);
  const loadKeys = useCallback(async (projectId: string) => {
    const data = await request<{ keys: Key[] }>(`/api/projects/${projectId}/keys`);
    setKeys(data.keys);
  }, []);
  useEffect(() => { loadProjects().catch((cause) => setError(cause.message)); }, [loadProjects]);
  useEffect(() => {
    setRevealed(""); setKeys([]);
    if (selected) loadKeys(selected).catch((cause) => setError(cause.message));
  }, [selected, loadKeys]);

  async function createProject(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const data = await request<{ project: Project }>("/api/projects", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ app_id: appId.trim(), name: name.trim() }),
      });
      await loadProjects(); setSelected(data.project.id); setAppId(""); setName("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create project"); }
    finally { setBusy(false); }
  }

  async function createKey() {
    setBusy(true); setError(""); setRevealed("");
    try {
      const data = await request<{ api_key: Key & { key: string } }>(`/api/projects/${selected}/keys`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scopes }),
      });
      setRevealed(data.api_key.key); setCopied(false); await loadKeys(selected);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create key"); }
    finally { setBusy(false); }
  }

  async function revoke(keyId: string) {
    setBusy(true); setError("");
    try {
      await request(`/api/projects/${selected}/keys/${keyId}`, { method: "DELETE" });
      await loadKeys(selected);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not revoke key"); }
    finally { setBusy(false); }
  }

  return <section id="project-keys" className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 card-shadow">
    <div className="flex items-center gap-2"><KeyRound size={18} /><h2 className="font-semibold">Projects and API keys</h2></div>
    <p className="mt-2 text-sm text-slate-500">Create a project key for your worker and SDK. Sign in with Google to manage it.</p>
    {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <form onSubmit={createProject} className="mt-5 flex flex-wrap gap-2">
      <input aria-label="Project app ID" required value={appId} onChange={(event) => setAppId(event.target.value)} placeholder="app_id" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" />
      <input aria-label="Project name" required value={name} onChange={(event) => setName(event.target.value)} placeholder="Project name" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" />
      <button disabled={busy} className="rounded-xl bg-slate-950 px-4 py-2 text-sm text-white disabled:opacity-50">Create project</button>
    </form>
    {projects.length > 0 && <div className="mt-6">
      <label className="text-sm font-medium" htmlFor="key-project">Project</label>
      <select id="key-project" value={selected} onChange={(event) => setSelected(event.target.value)} className="ml-3 rounded-xl border border-slate-300 px-3 py-2 text-sm">
        {projects.map((project) => <option key={project.id} value={project.id}>{project.name} ({project.app_id})</option>)}
      </select>
      <div className="mt-5 flex flex-wrap items-center gap-4">
        {allScopes.map((scope) => <label key={scope} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={scopes.includes(scope)} onChange={() => setScopes((current) => current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope])} />{scope}</label>)}
        <button type="button" onClick={() => void createKey()} disabled={busy || scopes.length === 0} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Create API key</button>
      </div>
      {revealed && <div className="mt-5 rounded-xl border border-amber-300 bg-amber-50 p-4">
        <p className="text-sm font-medium text-amber-900">Copy this key now. It will not be shown again.</p>
        <div className="mt-3 flex flex-wrap items-center gap-2"><code className="break-all text-sm">{revealed}</code><button type="button" onClick={() => { void navigator.clipboard.writeText(revealed).then(() => setCopied(true)); }} className="flex items-center gap-1 rounded-lg border border-amber-400 px-2 py-1 text-sm">{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "Copied" : "Copy"}</button><button type="button" onClick={() => setRevealed("")} className="text-sm underline">Hide</button></div>
      </div>}
      {onboarding && (revealed || keys.some((key) => !key.revoked_at && (!key.expires_at || new Date(key.expires_at).getTime() > Date.now()))) && <a href="/app" className="mt-4 inline-block rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white">Continue to app</a>}
      <div className="mt-5 divide-y divide-slate-100">{keys.map((key) => <div key={key.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><code>spk_{key.prefix}_…</code><p className="mt-1 text-slate-500">{key.scopes.join(", ")} · Last used: {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}{key.revoked_at ? " · Revoked" : ""}</p></div>{!key.revoked_at && <button type="button" onClick={() => void revoke(key.id)} disabled={busy} className="text-red-700 disabled:opacity-50">Revoke</button>}</div>)}{keys.length === 0 && <p className="py-3 text-sm text-slate-500">No keys yet.</p>}</div>
    </div>}
  </section>;
}
