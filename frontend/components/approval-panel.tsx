"use client";

import { Check, GitPullRequestArrow, LoaderCircle } from "lucide-react";
import { useState } from "react";

export function ApprovalPanel() {
  const [state, setState] = useState<"ready" | "approving" | "approved">("ready");

  function approve() {
    setState("approving");
    window.setTimeout(() => setState("approved"), 850);
  }

  return (
    <div className="rounded-2xl bg-blue-600 p-6 text-white card-shadow">
      <div className="flex items-center justify-between"><span className="mono text-[10px] uppercase tracking-[.18em] text-blue-100">Approval boundary</span><GitPullRequestArrow size={18} /></div>
      {state === "approved" ? (
        <><div className="mt-10 grid size-10 place-items-center rounded-full bg-white text-blue-700"><Check size={19} /></div><h3 className="mt-5 text-2xl font-semibold tracking-[-.04em]">Approved in this prototype.</h3><p className="mt-3 text-sm leading-6 text-blue-100">The production action can create the PR once GitHub and the backend approval endpoint are connected.</p></>
      ) : (
        <><h3 className="mt-10 text-2xl font-semibold tracking-[-.04em]">The fix is ready. You decide when it moves.</h3><p className="mt-3 text-sm leading-6 text-blue-100">Approval here only demonstrates the frontend state. It does not write code or contact GitHub.</p><button onClick={approve} disabled={state === "approving"} className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-white text-sm font-medium text-blue-700 disabled:opacity-70">{state === "approving" ? <><LoaderCircle size={15} className="animate-spin" />Recording approval…</> : <>Approve proposed fix <GitPullRequestArrow size={15} /></>}</button></>
      )}
    </div>
  );
}
