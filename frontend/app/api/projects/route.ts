import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { controlRequest } from "@/lib/server/control";

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  return controlRequest(user, "/internal/projects");
}

export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { app_id?: unknown; name?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  const appId = typeof body.app_id === "string" ? body.app_id.trim() : "";
  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(appId)) return badRequest("Enter a valid app ID");
  if (!name || name.length > 100) return badRequest("Enter a project name up to 100 characters");
  return controlRequest(user, "/internal/projects", "POST", { app_id: appId, name });
}
