import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { connection, neatlogsBackend, ownsAgent } from "@/lib/server/neatlogs";

export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { project_id?: unknown; workflow_name?: unknown; finding_id?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  if (typeof body.project_id !== "string" || typeof body.workflow_name !== "string" ||
      !ownsAgent(user.id, body.project_id, body.workflow_name))
    return NextResponse.json({ error: "Agent not found" }, { status: 404 });
  if (typeof body.finding_id !== "string" || !/^[a-f0-9]{16}$/.test(body.finding_id))
    return badRequest("Select a finding");
  const saved = connection(user.id);
  if (!saved) return NextResponse.json({ error: "Connect a NeatLogs read token" }, { status: 409 });
  try {
    const result = await neatlogsBackend("/v1/neatlogs/investigations", {
      user_id: user.id, project_id: body.project_id, workflow_name: body.workflow_name,
      finding_id: body.finding_id, ...saved,
    });
    return NextResponse.json(result.data, { status: result.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Investigation is unavailable" }, { status: 502 });
  }
}
