import { DashboardShell } from "@/components/dashboard-shell";
import { currentUser } from "@/lib/server/auth";
import { redirect } from "next/navigation";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  if (!await currentUser()) redirect("/api/auth/google/start");
  return <DashboardShell>{children}</DashboardShell>;
}
