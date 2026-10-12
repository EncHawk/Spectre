import "server-only";
import { db, decrypt } from "./db";
import { backendUrl } from "./backend";

const API = "https://api.github.com";
export async function github(path: string, token: string) {
  const response = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" },
    cache: "no-store", signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`GitHub API returned ${response.status}`);
  return response.json();
}
export function githubToken(userId: string) {
  const row = db().prepare("SELECT token FROM github_connections WHERE user_id=?").get(userId) as { token: string } | undefined;
  return row ? decrypt(row.token) : null;
}
export function parseRepo(value: string) {
  const trimmed = value.trim().replace(/^https:\/\/github\.com\//, "").replace(/\.git$/, "").replace(/\/$/, "");
  return /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(trimmed) ? trimmed : null;
}
export async function ingestRepo(userId: string, fullName: string) {
  const token = githubToken(userId);
  if (!token) throw new Error("Connect GitHub first");
  const repo = await github(`/repos/${fullName}`, token);
  if (repo.full_name?.toLowerCase() !== fullName.toLowerCase()) throw new Error("Repository identity mismatch");
  const branch = String(repo.default_branch);
  const branchInfo = await github(`/repos/${fullName}/branches/${encodeURIComponent(branch)}`, token);
  const sha = String(branchInfo.commit?.sha || "");
  const treeSha = String(branchInfo.commit?.commit?.tree?.sha || "");
  if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error("GitHub did not return a commit SHA");
  if (!/^[a-f0-9]{40}$/.test(treeSha)) throw new Error("GitHub did not return a tree SHA");
  const tree = await github(`/repos/${fullName}/git/trees/${treeSha}?recursive=1`, token);
  if (tree.truncated) throw new Error("Repository tree is too large for a complete snapshot");
  const files = (tree.tree as Array<{ path: string; type: string; size?: number }>).filter((entry) => entry.type === "blob")
    .map((entry) => ({ path: entry.path, size: entry.size ?? 0 }));
  if (files.length > 20000) throw new Error("Repository has more than 20,000 files");
  const { url: checkoutUrl, token: serviceToken } = backendUrl("/v1/repositories");
  const checkout = await fetch(checkoutUrl, {
    method: "POST", cache: "no-store", signal: AbortSignal.timeout(130000),
    headers: { Authorization: `Bearer ${serviceToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, full_name: repo.full_name, commit_sha: sha, github_token: token }),
  });
  if (!checkout.ok) throw new Error(`Diagnostics backend could not ingest checkout (${checkout.status})`);
  db().prepare(`INSERT INTO repositories(user_id,full_name,default_branch,commit_sha,file_count,indexed_at,files_json)
    VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,full_name) DO UPDATE SET
    default_branch=excluded.default_branch,commit_sha=excluded.commit_sha,file_count=excluded.file_count,
    indexed_at=excluded.indexed_at,files_json=excluded.files_json`)
    .run(userId, repo.full_name, branch, sha, files.length, new Date().toISOString(), JSON.stringify(files));
  return db().prepare(`SELECT id, full_name, default_branch, commit_sha, file_count, indexed_at FROM repositories
    WHERE user_id=? AND full_name=?`).get(userId, repo.full_name);
}
