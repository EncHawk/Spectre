import { NextRequest, NextResponse } from "next/server";
import { challenge, origin, random, setOAuth } from "@/lib/server/auth";
import { encrypt } from "@/lib/server/db";

export async function GET(request: NextRequest) {
  const base = origin(request);
  const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID;
  if (!clientId) return NextResponse.json({ error: "Google OAuth is not configured" }, { status: 503 });
  const state = random(); const verifier = random();
  const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  url.search = new URLSearchParams({ client_id: clientId, redirect_uri: `${base}/api/auth/google/callback`, response_type: "code",
    scope: "openid email profile", state, code_challenge: challenge(verifier), code_challenge_method: "S256", prompt: "select_account" }).toString();
  const response = NextResponse.redirect(url);
  setOAuth(response, encrypt(JSON.stringify({ kind: "google", state, verifier })));
  return response;
}
