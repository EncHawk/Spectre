import { NextRequest, NextResponse } from "next/server";
import { clearOAuth, equal, origin, OAUTH_COOKIE, requestUser } from "@/lib/server/auth";
import { db, encrypt, decrypt } from "@/lib/server/db";
import { github } from "@/lib/server/github";

export async function GET(request: NextRequest) {
  const base = origin(request); const user = requestUser(request);
  const saved = request.cookies.get(OAUTH_COOKIE)?.value;
  let flow: { kind: string; state: string; userId: string };
  try { flow = JSON.parse(decrypt(saved || "")); }
  catch { return NextResponse.redirect(`${base}/app?github_error=state`); }
  const code = request.nextUrl.searchParams.get("code"); const state = request.nextUrl.searchParams.get("state");
  if (!user || flow.kind !== "github" || flow.userId !== user.id || !state || !equal(flow.state, state) || !code)
    return NextResponse.redirect(`${base}/app?github_error=state`);
  try {
    const tokenResponse = await fetch("https://github.com/login/oauth/access_token", { method: "POST", cache: "no-store",
      headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify({
        client_id: process.env.GITHUB_OAUTH_CLIENT_ID, client_secret: process.env.GITHUB_OAUTH_CLIENT_SECRET,
        code, redirect_uri: `${base}/api/auth/github/callback`,
      }) });
    if (!tokenResponse.ok) throw new Error("GitHub token exchange failed");
    const tokenResult = await tokenResponse.json();
    if (!tokenResult.access_token || tokenResult.error) throw new Error("GitHub denied access");
    const profile = await github("/user", tokenResult.access_token);
    if (!profile.login) throw new Error("GitHub profile missing login");
    db().prepare(`INSERT INTO github_connections(user_id,login,token) VALUES(?,?,?)
      ON CONFLICT(user_id) DO UPDATE SET login=excluded.login,token=excluded.token`)
      .run(user.id, profile.login, encrypt(tokenResult.access_token));
    const response = NextResponse.redirect(`${base}/app#repositories`);
    clearOAuth(response); return response;
  } catch {
    const response = NextResponse.redirect(`${base}/app?github_error=connection`);
    clearOAuth(response); return response;
  }
}
