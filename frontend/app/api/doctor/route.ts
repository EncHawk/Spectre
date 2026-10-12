import { NextRequest, NextResponse } from "next/server";
import { requestUser, unauthorized } from "@/lib/server/auth";
import { db } from "@/lib/server/db";
import { backendUrl } from "@/lib/server/backend";

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  const appId = request.nextUrl.searchParams.get("app_id");
  if (!appId) return NextResponse.json({ error: "Select an agent" }, { status: 400 });
  const agent = db().prepare(`SELECT a.app_id,a.name,a.description,r.full_name,r.commit_sha,r.file_count
    FROM agents a LEFT JOIN repositories r ON r.id=a.repository_id WHERE a.user_id=? AND a.app_id=?`)
    .get(user.id, appId) as { app_id: string; name: string; description: string; full_name: string | null; commit_sha: string | null; file_count: number | null } | undefined;
  if (!agent) return NextResponse.json({ error: "Agent not found" }, { status: 404 });
  let url: URL; let token: string;
  try { ({ url, token } = backendUrl("/v1/doctor")); }
  catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Diagnostics backend is not configured" }, { status: 503 }); }
  url.searchParams.set("app_id", agent.app_id); url.searchParams.set("since", "30d"); url.searchParams.set("limit", "1000");
  if (agent.full_name && agent.commit_sha) {
    url.searchParams.set("user_id", user.id);
    url.searchParams.set("repository", agent.full_name);
    url.searchParams.set("commit_sha", agent.commit_sha);
  }
  try {
    const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error(`Diagnostics backend returned ${response.status}`);
    const report = await response.json();
    const repo = agent.full_name ? { full_name: agent.full_name, commit_sha: agent.commit_sha,
      file_count: agent.file_count, code_graph: report.repository?.code_graph || null } : null;
    for (const row of report.rows || []) {
      if (!repo) row.candidate_locations = [];
      const evidence = repo ? row.copy_to_agent :
        `Investigate Spectre finding ${row.finding.id}. Trace: ${row.finding.trace_id}; session: ${row.session_id}. ` +
        `Observed: ${row.finding.reason}. Suggested check: ${row.suggestion}. Connect a repository before editing code.`;
      row.copy_to_agent = `${evidence}\nAgent definition: ${agent.name} (${agent.app_id}). Intent: ${agent.description}. ` +
        `Pinned repository: ${repo?.full_name || "not connected"} at ${repo?.commit_sha || "unknown commit"}. ` +
        `Verify the root cause, test the suggested change, and summarize the evidence.`;
    }
    return NextResponse.json({ agent: { app_id: agent.app_id, name: agent.name, description: agent.description }, repository: repo,
      generated_at: report.generated_at, trace_count: report.trace_count, finding_count: report.finding_count, rows: report.rows, runs: report.runs || [] },
      { headers: { "Cache-Control": "no-store" } });
  } catch (error) { return NextResponse.json({ error: error instanceof Error ? error.message : "Diagnostics unavailable" }, { status: 502 }); }
}
