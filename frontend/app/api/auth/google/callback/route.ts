import { NextRequest, NextResponse } from "next/server";
import { allowedEmail, clearOAuth, equal, origin, OAUTH_COOKIE, setSession } from "@/lib/server/auth";
import { createSession, decrypt } from "@/lib/server/db";

export async function GET(request: NextRequest) {
  const base = origin(request);
  const saved = request.cookies.get(OAUTH_COOKIE)?.value;
  let flow: { kind: string; state: string; verifier: string };
  try { flow = JSON.parse(decrypt(saved || "")); }
  catch { return NextResponse.redirect(`${base}/?auth_error=state`); }
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  if (flow.kind !== "google" || !state || !equal(flow.state, state) || !code) return NextResponse.redirect(`${base}/?auth_error=state`);
  try {
    const tokenResponse = await fetch("https://oauth2.googleapis.com/token", { method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({
        code, client_id: process.env.GOOGLE_OAUTH_CLIENT_ID || "", client_secret: process.env.GOOGLE_OAUTH_CLIENT_SECRET || "",
        redirect_uri: `${base}/api/auth/google/callback`, grant_type: "authorization_code", code_verifier: flow.verifier,
      }) });
    if (!tokenResponse.ok) throw new Error("Google token exchange failed");
    const token = await tokenResponse.json();
    const profileResponse = await fetch("https://openidconnect.googleapis.com/v1/userinfo", {
      headers: { Authorization: `Bearer ${token.access_token}` }, cache: "no-store",
    });
    if (!profileResponse.ok) throw new Error("Google profile fetch failed");
    const profile = await profileResponse.json();
    if (!profile.sub || !profile.email || profile.email_verified !== true || !allowedEmail(String(profile.email)))
      throw new Error("Google account is not allowed");
    const session = createSession({ id: String(profile.sub), email: String(profile.email), name: String(profile.name || profile.email) });
    const response = NextResponse.redirect(`${base}/app`);
    setSession(response, session); clearOAuth(response);
    return response;
  } catch {
    const response = NextResponse.redirect(`${base}/?auth_error=google`);
    clearOAuth(response); return response;
  }
}
