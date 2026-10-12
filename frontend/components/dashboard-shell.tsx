"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, LayoutDashboard, Menu, ScanSearch, TestTubeDiagonal, X } from "lucide-react";
import { useState } from "react";
import { Logo } from "./logo";

const navigation = [
  { href: "/app", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/app/investigation", label: "Investigation", icon: TestTubeDiagonal },
  { href: "/app#neatlogs", label: "NeatLogs", icon: ScanSearch },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const sidebar = (
    <>
      <div className="flex h-[72px] items-center justify-between px-5"><Logo href="/app" /><button onClick={() => setOpen(false)} className="lg:hidden"><X size={20} /></button></div>
      <div className="px-3 pt-5">
        <p className="mono px-3 text-[10px] uppercase tracking-[.18em] text-slate-400">Workspace</p>
        <nav className="mt-3 space-y-1">
          {navigation.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : item.href === "/app/investigation" && pathname.startsWith("/app/investigation");
            const Icon = item.icon;
            return <Link onClick={() => setOpen(false)} key={item.label} href={item.href} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${active ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"}`}><Icon size={17} />{item.label}</Link>;
          })}
        </nav>
      </div>
      <div className="mt-auto border-t border-slate-200 p-3">
        <Link href="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-100"><BookOpen size={17} />Product site</Link>
        <form action="/api/auth/logout" method="post"><button className="w-full rounded-xl px-3 py-2.5 text-left text-sm text-slate-600 hover:bg-slate-100">Sign out</button></form>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-neutral-100 text-slate-950">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-slate-200 bg-[#f8fafc] lg:flex">{sidebar}</aside>
      {open && <aside className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white shadow-2xl lg:hidden">{sidebar}</aside>}
      {open && <button aria-label="Close navigation" onClick={() => setOpen(false)} className="fixed inset-0 z-40 bg-slate-950/20 lg:hidden" />}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-slate-200 bg-neutral-100/90 px-4 backdrop-blur md:px-8">
          <div className="flex items-center gap-3"><button onClick={() => setOpen(true)} className="rounded-lg p-2 hover:bg-white lg:hidden"><Menu size={20} /></button><span className="text-sm font-medium">Spectre workspace</span></div>
          <div className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">Connected control plane</div>
        </header>
        <div className="mx-auto max-w-[1440px] p-4 md:p-8">{children}</div>
      </div>
    </div>
  );
}
