import { NextRequest, NextResponse } from "next/server";
import { origin, sameOrigin, SESSION_COOKIE } from "@/lib/server/auth";
import { db, sha256 } from "@/lib/server/db";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (token) db().prepare("DELETE FROM sessions WHERE hash=?").run(sha256(token));
  const response = NextResponse.redirect(new URL("/", origin(request)), 303);
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
