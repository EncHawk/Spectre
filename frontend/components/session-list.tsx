"use client";

import Link from "next/link";
import { ArrowUpRight, Filter, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { sessions } from "@/lib/sample-data";
import { StatusPill } from "./status-pill";

export function SessionList() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const filtered = useMemo(() => sessions.filter((session) => {
    const matchesQuery = `${session.agent} ${session.repository} ${session.id}`.toLowerCase().includes(query.toLowerCase());
    const matchesFilter = filter === "all" || session.status === filter;
    return matchesQuery && matchesFilter;
  }), [filter, query]);

  return (
    <>
      <div className="mt-8 flex flex-col gap-3 md:flex-row">
        <label className="flex h-11 flex-1 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm text-slate-400"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} className="w-full bg-transparent text-slate-950 outline-none placeholder:text-slate-400" placeholder="Search agent, repository, or session ID" /></label>
        <label className="flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm text-slate-500"><Filter size={15} /><select value={filter} onChange={(event) => setFilter(event.target.value)} className="bg-transparent outline-none"><option value="all">All statuses</option><option value="running">Running</option><option value="needs-approval">Needs approval</option><option value="investigating">Investigating</option><option value="healthy">Healthy</option></select></label>
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white card-shadow">
        <div className="hidden grid-cols-[1.5fr_.9fr_.7fr_.7fr_40px] gap-4 border-b border-slate-200 bg-slate-50 px-5 py-3 text-[10px] uppercase tracking-[.15em] text-slate-400 md:grid">
          <span>Session</span><span>Status</span><span>Runs</span><span>Next step</span><span />
        </div>
        <div className="divide-y divide-slate-100">
          {filtered.map((session) => (
            <Link key={session.id} href={`/app/sessions/${session.id}`} className="grid gap-4 p-5 transition hover:bg-neutral-100 md:grid-cols-[1.5fr_.9fr_.7fr_.7fr_40px] md:items-center">
              <div><div className="flex items-center gap-2"><span className="font-medium">{session.agent}</span><span className="mono text-[10px] text-slate-400">{session.id}</span></div><p className="mono mt-2 text-xs text-slate-400">{session.repository} · {session.branch}</p></div>
              <div><StatusPill status={session.status} /></div>
              <div><p className="text-sm">{session.runs} total</p><p className="mt-1 text-xs text-slate-400">{session.failures} failures</p></div>
              <div><p className="text-sm">{session.fix}</p><p className="mt-1 text-xs text-slate-400">Started {session.started}</p></div>
              <ArrowUpRight size={17} className="text-slate-400" />
            </Link>
          ))}
          {filtered.length === 0 && <div className="p-12 text-center text-sm text-slate-500">No sessions match this view.</div>}
        </div>
      </div>
    </>
  );
}
