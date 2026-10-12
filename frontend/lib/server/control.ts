import "server-only";
import { NextResponse } from "next/server";
import { backendUrl } from "./backend";
import type { User } from "./db";

export async function hasActiveProjectKey(user: User): Promise<boolean> {
  const { url, token } = backendUrl("/internal/access");
  const response = await fetch(url, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
    headers: { Authorization: `Bearer ${token}`, "X-Spectre-User-Id": user.id },
  });
  if (!response.ok) throw new Error("Control service unavailable");
  const data: unknown = await response.json();
  if (!data || typeof data !== "object" || !("has_active_key" in data) ||
      typeof data.has_active_key !== "boolean") throw new Error("Invalid control service response");
  return data.has_active_key;
}

export async function controlRequest(user: User, path: string, method = "GET", body?: unknown) {
  let url: URL; let token: string;
  try { ({ url, token } = backendUrl(path)); }
  catch { return NextResponse.json({ error: "Control service is not configured" }, { status: 503 }); }
  try {
    const response = await fetch(url, {
      method, cache: "no-store", signal: AbortSignal.timeout(10000),
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Spectre-User-Id": user.id,
        "X-Spectre-User-Email": user.email,
        "X-Spectre-User-Name": user.name,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Control service unavailable" }, { status: 502 });
  }
}
