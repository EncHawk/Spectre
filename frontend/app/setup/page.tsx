import { currentUser } from "@/lib/server/auth";
import { ProjectKeys } from "@/components/project-keys";
import { redirect } from "next/navigation";

export default async function SetupPage() {
  if (!await currentUser()) redirect("/");
  return <main className="mx-auto max-w-3xl p-6 text-slate-950 md:p-12">
    <p className="text-xs font-medium uppercase tracking-widest text-blue-700">Spectre setup</p>
    <h1 className="mt-3 text-3xl font-semibold">Create a project key to enter the workspace</h1>
    <p className="mt-3 text-slate-600">Your Google session is active. Create a project, mint a key, and copy it for your worker or SDK.</p>
    <ProjectKeys onboarding />
    <form action="/api/auth/logout" method="post" className="mt-6"><button className="text-sm text-slate-600 underline">Sign out</button></form>
  </main>;
}
