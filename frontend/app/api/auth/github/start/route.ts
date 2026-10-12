import { NextRequest, NextResponse } from "next/server";
import { origin, random, requestUser, setOAuth } from "@/lib/server/auth";
import { encrypt } from "@/lib/server/db";

export async function GET(request: NextRequest) {
  const base = origin(request);
  const user = requestUser(request);
  if (!user) return NextResponse.redirect(`${base}/api/auth/google/start`);
  const clientId = process.env.GITHUB_OAUTH_CLIENT_ID;
  if (!clientId) return NextResponse.json({ error: "GitHub OAuth is not configured" }, { status: 503 });
  const state = random();
  const url = new URL("https://github.com/login/oauth/authorize");
  url.search = new URLSearchParams({ client_id: clientId, redirect_uri: `${base}/api/auth/github/callback`, scope: "repo read:user", state }).toString();
  const response = NextResponse.redirect(url);
  setOAuth(response, encrypt(JSON.stringify({ kind: "github", state, userId: user.id })));
  return response;
}
