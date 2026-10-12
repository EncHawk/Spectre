import { NextRequest, NextResponse } from "next/server";
import { requestUser, unauthorized } from "@/lib/server/auth";
import { connection, neatlogsBackend, ownsAgent } from "@/lib/server/neatlogs";

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  const projectId = request.nextUrl.searchParams.get("project_id") || "";
  const workflowName = request.nextUrl.searchParams.get("workflow_name") || "";
  if (!ownsAgent(user.id, projectId, workflowName)) return NextResponse.json({ error: "Agent not found" }, { status: 404 });
  const saved = connection(user.id);
  if (!saved) return NextResponse.json({ error: "Connect a NeatLogs read token" }, { status: 409 });
  try {
    const result = await neatlogsBackend("/v1/neatlogs/doctor", { user_id: user.id,
      project_id: projectId, workflow_name: workflowName, ...saved });
    return NextResponse.json(result.data, { status: result.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "NeatLogs traces are unavailable" }, { status: 502 });
  }
}
