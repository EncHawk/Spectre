import { DashboardShell } from "@/components/dashboard-shell";
import { currentUser } from "@/lib/server/auth";
import { hasActiveProjectKey } from "@/lib/server/control";
import { redirect } from "next/navigation";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect("/");
  let hasKey: boolean;
  try { hasKey = await hasActiveProjectKey(user); }
  catch { return <main className="mx-auto max-w-xl p-8"><h1 className="text-2xl font-semibold">Workspace unavailable</h1><p className="mt-3 text-slate-600">The key service could not be reached. Try again shortly.</p><a className="mt-4 inline-block text-blue-700 underline" href="/">Return home</a></main>; }
  if (!hasKey) redirect("/setup");
  return <DashboardShell>{children}</DashboardShell>;
}
