import { Logo } from "@/components/logo";
import { currentUser } from "@/lib/server/auth";
import { ArrowRight, ScanSearch } from "lucide-react";
import { redirect } from "next/navigation";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ auth_error?: string }> }) {
  if (await currentUser()) redirect("/app");
  const { auth_error: authError } = await searchParams;

  return <main className="flex min-h-screen items-center justify-center bg-neutral-100 px-4 py-12 text-slate-950">
    <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-[0_20px_70px_rgba(15,23,42,.08)] sm:p-10">
      <Logo />
      <div className="mt-10 grid size-12 place-items-center rounded-2xl bg-blue-50 text-blue-700"><ScanSearch size={23} /></div>
      <h1 className="mt-5 text-3xl font-semibold tracking-tight">Sign in to your workspace</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">Sign in with your Google account. Then connect your NeatLogs read token, choose a project, and select an agent from its traces.</p>
      {authError && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">Sign-in failed. Try again with an authorized Google account.</p>}
      <a href="/api/auth/google/start" className="mt-8 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700">Continue with Google <ArrowRight size={16} /></a>
      <p className="mt-5 text-center text-xs text-slate-500">Workspace access is limited to authorized accounts.</p>
    </div>
  </main>;
}
