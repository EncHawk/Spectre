import { NextRequest, NextResponse } from "next/server";
import { badRequest, requestUser, sameOrigin, unauthorized } from "@/lib/server/auth";
import { backendUrl } from "@/lib/server/backend";

const EXAMPLES = new Set(["checkout_support", "research_brief"]);

export async function POST(request: NextRequest) {
  if (!requestUser(request)) return unauthorized();
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: { example?: unknown };
  try { body = await request.json(); } catch { return badRequest("Invalid JSON body"); }
  if (typeof body.example !== "string" || !EXAMPLES.has(body.example)) return badRequest("Select a listed example");
  try {
    const { url, token } = backendUrl("/v1/example-runs");
    const response = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify({ example: body.example }), cache: "no-store", signal: AbortSignal.timeout(60000) });
    const value = await response.json();
    if (!response.ok) return NextResponse.json({ error: value.error || `Examples backend returned ${response.status}` }, { status: 502 });
    return NextResponse.json(value, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Example run failed" }, { status: 502 });
  }
}
