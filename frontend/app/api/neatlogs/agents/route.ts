import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { db } from "@/lib/server/db";
import { connection, neatlogsBackend, ownsProject } from "@/lib/server/neatlogs";

export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { project_id?: unknown; workflow_name?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  const projectId = typeof body.project_id === "string" ? body.project_id : "";
  const workflowName = typeof body.workflow_name === "string" ? body.workflow_name : "";
  if (!ownsProject(user.id, projectId)) return NextResponse.json({ error: "Project not found" }, { status: 404 });
  if (!workflowName || workflowName.length > 255) return badRequest("Select a workflow");
  const saved = connection(user.id);
  if (!saved) return NextResponse.json({ error: "Connect a NeatLogs read token" }, { status: 409 });
  try {
    const result = await neatlogsBackend("/v1/neatlogs/workflows", { project_id: projectId, ...saved });
    if (result.status !== 200) return NextResponse.json(result.data, { status: result.status });
    if (!Array.isArray(result.data.workflows) || !result.data.workflows.includes(workflowName))
      return badRequest("Workflow was not found in this project’s traces");
    db().prepare(`INSERT INTO neatlogs_agents(user_id,project_id,workflow_name,selected_at) VALUES(?,?,?,?)
      ON CONFLICT(user_id,project_id,workflow_name) DO UPDATE SET selected_at=excluded.selected_at`)
      .run(user.id, projectId, workflowName, new Date().toISOString());
    return NextResponse.json({ project_id: projectId, workflow_name: workflowName }, { status: 201 });
  } catch {
    return NextResponse.json({ error: "Could not save the selected agent" }, { status: 502 });
  }
}
