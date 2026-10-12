import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { db, encrypt } from "@/lib/server/db";
import { connection, neatlogsBackend, NEATLOGS_HOSTS } from "@/lib/server/neatlogs";

const noStore = { "Cache-Control": "no-store" };
type DiscoveredProject = { id: string; name: string; role: string };

export async function GET(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  const saved = db().prepare("SELECT host, updated_at FROM neatlogs_connections WHERE user_id=?")
    .get(user.id) as { host: string; updated_at: string } | undefined;
  const projects = db().prepare(`SELECT project_id, name, role FROM neatlogs_projects
    WHERE user_id=? AND available=1 ORDER BY name COLLATE NOCASE`).all(user.id);
  const agents = db().prepare(`SELECT a.project_id, a.workflow_name FROM neatlogs_agents a
    JOIN neatlogs_projects p ON p.user_id=a.user_id AND p.project_id=a.project_id
    WHERE a.user_id=? AND p.available=1 ORDER BY a.selected_at DESC`).all(user.id);
  return NextResponse.json({ connected: Boolean(saved), host: saved?.host || NEATLOGS_HOSTS[0],
    token_updated_at: saved?.updated_at || null, projects, agents }, { headers: noStore });
}

export async function POST(request: NextRequest) {
  const user = requestUser(request); if (!user) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { read_token?: unknown; host?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  const supplied = typeof body.read_token === "string" ? body.read_token.trim() : "";
  if (supplied.length > 8192) return badRequest("Read token is too long");
  const prior = connection(user.id);
  const host = body.host === undefined ? prior?.host || NEATLOGS_HOSTS[0] : body.host;
  if (typeof host !== "string" || !NEATLOGS_HOSTS.includes(host as typeof NEATLOGS_HOSTS[number]))
    return badRequest("Select a supported NeatLogs region");
  const readToken = supplied || prior?.read_token;
  if (!readToken) return badRequest("Enter a NeatLogs service-account read token");
  try {
    const discovery = await neatlogsBackend("/v1/neatlogs/projects", { read_token: readToken, host });
    if (discovery.status !== 200) return NextResponse.json({ error: discovery.data.error || "NeatLogs projects could not be listed" },
      { status: discovery.status === 401 || discovery.status === 403 ? discovery.status : 502, headers: noStore });
    const projects = discovery.data.projects as DiscoveredProject[];
    if (!Array.isArray(projects) || projects.some((item) => !item || typeof item.id !== "string" || typeof item.name !== "string"))
      return NextResponse.json({ error: "Invalid NeatLogs project list" }, { status: 502, headers: noStore });
    const now = new Date().toISOString();
    const database = db(); database.exec("BEGIN");
    try {
      database.prepare(`INSERT INTO neatlogs_connections(user_id,read_token,host,updated_at) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET read_token=excluded.read_token,host=excluded.host,updated_at=excluded.updated_at`)
        .run(user.id, encrypt(readToken), host, now);
      database.prepare("UPDATE neatlogs_projects SET available=0 WHERE user_id=?").run(user.id);
      const upsert = database.prepare(`INSERT INTO neatlogs_projects(user_id,project_id,added_at,name,role,available)
        VALUES(?,?,?,?,?,1) ON CONFLICT(user_id,project_id)
        DO UPDATE SET name=excluded.name,role=excluded.role,available=1`);
      for (const project of projects) upsert.run(user.id, project.id, now, project.name, project.role || "");
      database.exec("COMMIT");
    } catch (error) { database.exec("ROLLBACK"); throw error; }
    return NextResponse.json({ connected: true, projects }, { headers: noStore });
  } catch {
    return NextResponse.json({ error: "Could not discover or save NeatLogs projects" }, { status: 502, headers: noStore });
  }
}
