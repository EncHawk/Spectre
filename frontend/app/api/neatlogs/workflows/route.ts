import { NextRequest, NextResponse } from "next/server";
import { requestUser, unauthorized } from "@/lib/server/auth";
import { connection, neatlogsBackend, ownsProject } from "@/lib/server/neatlogs";

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  const projectId = request.nextUrl.searchParams.get("project_id") || "";
  if (!ownsProject(user.id, projectId)) return NextResponse.json({ error: "Project not found" }, { status: 404 });
  const saved = connection(user.id);
  if (!saved) return NextResponse.json({ error: "Connect a NeatLogs read token" }, { status: 409 });
  try {
    const result = await neatlogsBackend("/v1/neatlogs/workflows", { project_id: projectId, ...saved });
    return NextResponse.json(result.data, { status: result.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Could not list NeatLogs workflows" }, { status: 502 });
  }
}
