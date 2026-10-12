import { DashboardShell } from "@/components/dashboard-shell";
import { currentUser } from "@/lib/server/auth";
import { redirect } from "next/navigation";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect("/");
  return <DashboardShell>{children}</DashboardShell>;
}
