import { NextRequest, NextResponse } from "next/server";
import { requestUser, unauthorized } from "@/lib/server/auth";
import { backendUrl } from "@/lib/server/backend";

export async function GET(request: NextRequest) {
  if (!requestUser(request)) return unauthorized();
  try {
    const { url, token } = backendUrl("/v1/examples");
    const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error(`Examples backend returned ${response.status}`);
    return NextResponse.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Examples unavailable" }, { status: 502 });
  }
}
