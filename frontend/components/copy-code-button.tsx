"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

export function CopyCodeButton({ code }: { code: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setStatus("copied");
      window.setTimeout(() => setStatus("idle"), 1800);
    } catch {
      setStatus("error");
    }
  }

  return (
    <button
      type="button"
      onClick={copyCode}
      className="flex items-center gap-2 rounded-lg px-2 py-1 text-xs text-blue-200 hover:bg-white/10"
      aria-label={status === "error" ? "Copy failed; select the code manually" : undefined}
    >
      {status === "copied" ? <Check size={13} /> : <Copy size={13} />}
      {status === "copied" ? "Copied" : status === "error" ? "Copy failed" : "Copy code"}
    </button>
  );
}
