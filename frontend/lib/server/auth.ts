import "server-only";
import { randomBytes, createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { userForSession } from "./db";

export const SESSION_COOKIE = "spectre_session";
export const OAUTH_COOKIE = "spectre_oauth";
export const secure = process.env.NODE_ENV === "production";

function allowedEmail(email: string) {
  const configured = process.env.SPECTRE_ALLOWED_EMAILS || process.env.SPECTRE_ALLOWED_EMAIL;
  return Boolean(configured && configured.split(",").some((entry) => email.toLowerCase() === entry.trim().toLowerCase()));
}

export async function currentUser() {
  const user = userForSession((await cookies()).get(SESSION_COOKIE)?.value);
  return user && allowedEmail(user.email) ? user : null;
}

export function requestUser(request: NextRequest) {
  const user = userForSession(request.cookies.get(SESSION_COOKIE)?.value);
  return user && allowedEmail(user.email) ? user : null;
}

export { allowedEmail };

export function unauthorized() { return NextResponse.json({ error: "Sign in required" }, { status: 401 }); }
export function badRequest(message: string) { return NextResponse.json({ error: message }, { status: 400 }); }
export function random() { return randomBytes(32).toString("base64url"); }
export function challenge(verifier: string) { return createHash("sha256").update(verifier).digest("base64url"); }
export function equal(a: string, b: string) {
  const left = Buffer.from(a); const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}
export function origin(_request: NextRequest) {
  const configured = process.env.SPECTRE_PUBLIC_URL;
  if (!configured) throw new Error("SPECTRE_PUBLIC_URL is required");
  const value = new URL(configured);
  if (value.protocol !== "https:" && value.hostname !== "localhost" && value.hostname !== "127.0.0.1") throw new Error("SPECTRE_PUBLIC_URL must use HTTPS");
  return value.origin;
}
export function sameOrigin(request: NextRequest) {
  const expected = origin(request);
  const supplied = request.headers.get("origin");
  return supplied === expected;
}
export function setSession(response: NextResponse, token: string) {
  response.cookies.set(SESSION_COOKIE, token, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 30 * 24 * 3600 });
}
export function setOAuth(response: NextResponse, value: string) {
  response.cookies.set(OAUTH_COOKIE, value, { httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 600 });
}
export function clearOAuth(response: NextResponse) { response.cookies.delete(OAUTH_COOKIE); }
