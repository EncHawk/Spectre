import { SessionStatus, statusLabel } from "@/lib/sample-data";

const styles: Record<SessionStatus, string> = {
  running: "border-blue-200 bg-blue-50 text-blue-700",
  "needs-approval": "border-indigo-200 bg-indigo-50 text-indigo-700",
  healthy: "border-slate-200 bg-white text-slate-600",
  investigating: "border-sky-200 bg-sky-50 text-sky-700",
};

export function StatusPill({ status }: { status: SessionStatus }) {
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium ${styles[status]}`}>
      <span className={`size-1.5 rounded-full ${status === "healthy" ? "bg-slate-400" : "bg-blue-600"}`} />
      {statusLabel[status]}
    </span>
  );
}
