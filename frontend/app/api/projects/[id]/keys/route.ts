import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { controlRequest } from "@/lib/server/control";

type Context = { params: Promise<{ id: string }> };
const scopes = new Set(["runs:write", "runs:read", "jobs:pull"]);

export async function GET(request: NextRequest, { params }: Context) {
  const user = requestUser(request); if (!user) return unauthorized();
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return badRequest("Invalid project ID");
  return controlRequest(user, `/internal/projects/${id}/keys`);
}

export async function POST(request: NextRequest, { params }: Context) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return badRequest("Invalid project ID");
  let body: { scopes?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  if (!Array.isArray(body.scopes) || !body.scopes.length ||
      body.scopes.some((scope) => typeof scope !== "string" || !scopes.has(scope)) ||
      new Set(body.scopes).size !== body.scopes.length) return badRequest("Choose valid, distinct scopes");
  return controlRequest(user, `/internal/projects/${id}/keys`, "POST", { scopes: body.scopes });
}
