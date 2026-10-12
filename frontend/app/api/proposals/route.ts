import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { db } from "@/lib/server/db";
import { backendUrl } from "@/lib/server/backend";

export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { app_id?: unknown; finding_id?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  if (typeof body.app_id !== "string" || typeof body.finding_id !== "string" || !/^[a-f0-9]{16}$/.test(body.finding_id)) return badRequest("Select a finding and agent");
  const agent = db().prepare(`SELECT r.full_name,r.commit_sha FROM agents a JOIN repositories r ON r.id=a.repository_id
    WHERE a.user_id=? AND a.app_id=?`).get(user.id, body.app_id) as { full_name: string; commit_sha: string } | undefined;
  if (!agent) return badRequest("Link this agent to an ingested repository first");
  try {
    const { url, token } = backendUrl("/v1/proposals");
    const response = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: user.id, app_id: body.app_id, finding_id: body.finding_id,
        repository: agent.full_name, commit_sha: agent.commit_sha }), cache: "no-store", signal: AbortSignal.timeout(120000) });
    const value = await response.json();
    if (!response.ok) return NextResponse.json({ error: value.error || `Fix backend returned ${response.status}` }, { status: 502 });
    return NextResponse.json(value, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Fix proposal failed" }, { status: 502 });
  }
}
