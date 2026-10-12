"use client";

import { useState } from "react";

type Investigation = {
  evidence: { finding_id: string; trace_id: string; check: string; reason: string; invocation_path: string[] };
  likely_cause: string;
  suggested_fix: string;
  how_to_verify: string;
  model_status: string;
  basis: string;
};

export function InvestigationPanel({ appId, findingId }: { appId: string; findingId: string }) {
  const [result, setResult] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function investigate() {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/investigations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ app_id: appId, finding_id: findingId }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Investigation failed");
      setResult(value);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Investigation failed"); }
    finally { setBusy(false); }
  }

  async function copy() {
    if (!result) return;
    await navigator.clipboard.writeText(
      `Spectre investigation for ${appId}\nFinding: ${result.evidence.finding_id}\nTrace: ${result.evidence.trace_id}\nObserved: ${result.evidence.reason}\nLikely cause (hypothesis): ${result.likely_cause}\nSuggested fix: ${result.suggested_fix}\nHow to verify: ${result.how_to_verify}`
    );
  }

  return <div className="mt-4">
    <button disabled={busy} onClick={() => void investigate()} className="rounded-xl border border-blue-200 px-3 py-2 text-xs font-medium text-blue-700 disabled:opacity-50">{busy ? "Investigating…" : "Investigate and suggest fix"}</button>
    {error && <p role="alert" className="mt-2 text-xs text-red-700">{error}</p>}
    {result && <div className="mt-3 rounded-xl bg-slate-50 p-4 text-sm">
      <div className="flex items-center justify-between gap-3"><p className="font-semibold">Investigation</p><button onClick={() => void copy()} className="text-xs text-blue-700">Copy findings</button></div>
      <p className="mt-3"><strong>Likely cause:</strong> {result.likely_cause}</p>
      <p className="mt-2"><strong>Suggested fix:</strong> {result.suggested_fix}</p>
      <p className="mt-2"><strong>Verify it:</strong> {result.how_to_verify}</p>
      <p className="mt-3 text-xs text-slate-500">{result.basis} Analysis: {result.model_status === "used" ? "OpenAI assisted" : result.model_status === "not_configured" ? "rule-based; OpenAI not configured" : "rule-based fallback"}.</p>
    </div>}
  </div>;
}
