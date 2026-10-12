import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { controlRequest } from "@/lib/server/control";

type Context = { params: Promise<{ id: string; keyId: string }> };

export async function DELETE(request: NextRequest, { params }: Context) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  const { id, keyId } = await params;
  if (![id, keyId].every((value) => /^[0-9a-f-]{36}$/i.test(value))) return badRequest("Invalid ID");
  return controlRequest(user, `/internal/projects/${id}/keys/${keyId}`, "DELETE");
}
