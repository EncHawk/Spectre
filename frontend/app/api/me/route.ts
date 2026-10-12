import { NextRequest, NextResponse } from "next/server";
import { requestUser, unauthorized } from "@/lib/server/auth";
import { db } from "@/lib/server/db";

export async function GET(request: NextRequest) {
  const user = requestUser(request);
  if (!user) return unauthorized();
  const github = db().prepare("SELECT login FROM github_connections WHERE user_id=?").get(user.id) as { login: string } | undefined;
  return NextResponse.json({ user, github: github?.login ?? null });
}
