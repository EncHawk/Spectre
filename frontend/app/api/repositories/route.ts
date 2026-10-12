import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { db } from "@/lib/server/db";
import { githubToken, ingestRepo, parseRepo } from "@/lib/server/github";

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  const repositories = db().prepare(`SELECT id,full_name,default_branch,commit_sha,file_count,indexed_at
    FROM repositories WHERE user_id=? ORDER BY indexed_at DESC`).all(user.id);
  return NextResponse.json({ connected: Boolean(githubToken(user.id)), repositories });
}
export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { repository?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  const fullName = typeof body.repository === "string" ? parseRepo(body.repository) : null;
  if (!fullName) return badRequest("Enter a GitHub owner/repository name or URL");
  try { return NextResponse.json({ repository: await ingestRepo(user.id, fullName) }, { status: 201 }); }
  catch (error) { return badRequest(error instanceof Error ? error.message : "Repository ingestion failed"); }
}
