import "server-only";
import { backendUrl } from "./backend";
import { db, decrypt } from "./db";

export const NEATLOGS_HOSTS = ["https://app.neatlogs.com", "https://eu.app.neatlogs.com"] as const;
export type NeatlogsHost = typeof NEATLOGS_HOSTS[number];

export function connection(userId: string) {
  const row = db().prepare("SELECT read_token, host FROM neatlogs_connections WHERE user_id=?")
    .get(userId) as { read_token: string; host: NeatlogsHost } | undefined;
  return row ? { read_token: decrypt(row.read_token), host: row.host } : null;
}

export function ownsProject(userId: string, projectId: string) {
  return Boolean(db().prepare("SELECT 1 FROM neatlogs_projects WHERE user_id=? AND project_id=? AND available=1").get(userId, projectId));
}

export function ownsAgent(userId: string, projectId: string, workflowName: string) {
  return Boolean(db().prepare(`SELECT 1 FROM neatlogs_agents a JOIN neatlogs_projects p
    ON p.user_id=a.user_id AND p.project_id=a.project_id WHERE a.user_id=? AND a.project_id=?
    AND a.workflow_name=? AND p.available=1`).get(userId, projectId, workflowName));
}

export async function neatlogsBackend(path: string, payload: object) {
  const { url, token } = backendUrl(path);
  const response = await fetch(url, {
    method: "POST", cache: "no-store", signal: AbortSignal.timeout(path.endsWith("/probe") ? 120000 : 600000),
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  return { status: response.status, data };
}
