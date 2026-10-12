"use client";

import { ArrowRight, Check, GitBranch, X } from "lucide-react";
import { FormEvent, useState } from "react";

export function RepositoryPrompt() {
  const [open, setOpen] = useState(false);
  const [repo, setRepo] = useState("");
  const [saved, setSaved] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!repo.trim()) return;
    setSaved(true);
  }

  return (
    <>
      <button onClick={() => { setOpen(true); setSaved(false); }} className="inline-flex h-10 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-medium text-white transition hover:bg-blue-700"><GitBranch size={15} />Add repository</button>
      {open && (
        <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/25 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="repo-title">
          <div className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl md:p-8">
            <div className="flex items-start justify-between"><div className="grid size-11 place-items-center rounded-full bg-blue-50 text-blue-700"><GitBranch size={19} /></div><button aria-label="Close" onClick={() => setOpen(false)} className="rounded-full border border-slate-200 p-2 text-slate-500 hover:text-slate-950"><X size={16} /></button></div>
            {saved ? (
              <div className="py-6"><div className="grid size-12 place-items-center rounded-full bg-blue-600 text-white"><Check size={21} /></div><h2 id="repo-title" className="mt-5 text-3xl font-semibold tracking-[-.05em]">Context saved locally.</h2><p className="mt-3 leading-7 text-slate-600">The UI is ready to pass <span className="mono text-sm text-slate-950">{repo}</span> to the backend when repository access is connected.</p><button onClick={() => setOpen(false)} className="mt-7 rounded-full bg-slate-950 px-5 py-3 text-sm font-medium text-white">Done</button></div>
            ) : (
              <form onSubmit={submit}>
                <h2 id="repo-title" className="mt-6 text-3xl font-semibold tracking-[-.05em]">Where does your agent live?</h2>
                <p className="mt-3 leading-7 text-slate-600">Spectre uses repository context to understand the agent before suggesting a fix. No code is changed from this prototype.</p>
                <label className="mt-7 block text-sm font-medium" htmlFor="repo">GitHub repository</label>
                <input id="repo" required value={repo} onChange={(event) => setRepo(event.target.value)} placeholder="owner/repository or GitHub URL" className="mt-2 h-12 w-full rounded-xl border border-slate-300 bg-neutral-100 px-4 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
                <button type="submit" className="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 font-medium text-white transition hover:bg-blue-700">Continue with this repo <ArrowRight size={16} /></button>
                <p className="mt-4 text-center text-xs leading-5 text-slate-400">GitHub OAuth and backend persistence are intentionally not connected yet.</p>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
