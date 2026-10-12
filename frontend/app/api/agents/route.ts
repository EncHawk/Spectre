import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { db } from "@/lib/server/db";

const SELECT = `SELECT a.id,a.app_id,a.name,a.description,a.repository_id,a.created_at,
  r.full_name AS repository_name,r.commit_sha AS repository_commit FROM agents a
  LEFT JOIN repositories r ON r.id=a.repository_id WHERE a.user_id=?`;

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  return NextResponse.json({ agents: db().prepare(`${SELECT} ORDER BY a.created_at DESC`).all(user.id) });
}
export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { app_id?: unknown; name?: unknown; description?: unknown; repository_id?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  const appId = typeof body.app_id === "string" ? body.app_id.trim() : "";
  const name = typeof body.name === "string" ? body.name.trim() : "";
  const description = typeof body.description === "string" ? body.description.trim() : "";
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$/.test(appId)) return badRequest("app_id must be 1–64 letters, numbers, dots, underscores, or hyphens");
  if (!name || name.length > 100 || description.length > 2000) return badRequest("Enter a name up to 100 characters and description up to 2,000 characters");
  const repositoryId = body.repository_id === null || body.repository_id === undefined || body.repository_id === "" ? null : Number(body.repository_id);
  if (repositoryId !== null && (!Number.isSafeInteger(repositoryId) || !db().prepare("SELECT id FROM repositories WHERE id=? AND user_id=?").get(repositoryId, user.id)))
    return badRequest("Select one of your ingested repositories");
  try {
    db().prepare(`INSERT INTO agents(user_id,app_id,name,description,repository_id,created_at) VALUES(?,?,?,?,?,?)
      ON CONFLICT(user_id,app_id) DO UPDATE SET name=excluded.name,description=excluded.description,repository_id=excluded.repository_id`)
      .run(user.id, appId, name, description, repositoryId, new Date().toISOString());
    return NextResponse.json({ agent: db().prepare(`${SELECT} AND a.app_id=?`).get(user.id, appId) }, { status: 201 });
  } catch { return badRequest("Could not save agent"); }
}
