import "server-only";
import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

const path = resolve(process.env.SPECTRE_DB_PATH || ".spectre/control.sqlite");
let database: DatabaseSync | undefined;

export function db() {
  if (!database) {
    mkdirSync(dirname(path), { recursive: true });
    database = new DatabaseSync(path);
    database.exec("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000");
    database.exec(`
      CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires_at INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS github_connections (user_id TEXT PRIMARY KEY REFERENCES users(id), login TEXT NOT NULL, token TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS repositories (
        id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), full_name TEXT NOT NULL,
        default_branch TEXT NOT NULL, commit_sha TEXT NOT NULL, file_count INTEGER NOT NULL,
        indexed_at TEXT NOT NULL, files_json TEXT NOT NULL,
        UNIQUE(user_id, full_name)
      );
      CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), app_id TEXT NOT NULL,
        name TEXT NOT NULL, description TEXT NOT NULL, repository_id INTEGER REFERENCES repositories(id),
        created_at TEXT NOT NULL, UNIQUE(user_id, app_id)
      );
    `);
  }
  return database;
}

export function sha256(value: string) { return createHash("sha256").update(value).digest("hex"); }

function key() {
  const value = process.env.SPECTRE_ENCRYPTION_KEY;
  if (!value || !/^[a-f0-9]{64}$/i.test(value)) throw new Error("SPECTRE_ENCRYPTION_KEY must be 32 bytes in hex");
  return Buffer.from(value, "hex");
}

export function encrypt(value: string) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  const body = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  return [iv, cipher.getAuthTag(), body].map((part) => part.toString("base64url")).join(".");
}

export function decrypt(value: string) {
  const [nonce, tag, body] = value.split(".");
  if (!nonce || !tag || !body) throw new Error("Invalid encrypted token");
  const decipher = createDecipheriv("aes-256-gcm", key(), Buffer.from(nonce, "base64url"));
  decipher.setAuthTag(Buffer.from(tag, "base64url"));
  return Buffer.concat([decipher.update(Buffer.from(body, "base64url")), decipher.final()]).toString("utf8");
}

export type User = { id: string; email: string; name: string };
export function userForSession(token: string | undefined): User | null {
  if (!token) return null;
  return (db().prepare(`SELECT u.id, u.email, u.name FROM sessions s JOIN users u ON u.id=s.user_id
    WHERE s.hash=? AND s.expires_at>?`).get(sha256(token), Date.now()) as User | undefined) ?? null;
}

export function createSession(user: User) {
  const token = randomBytes(32).toString("base64url");
  db().prepare("INSERT INTO users(id,email,name) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET email=excluded.email,name=excluded.name")
    .run(user.id, user.email, user.name);
  db().prepare("INSERT INTO sessions(hash,user_id,expires_at) VALUES(?,?,?)")
    .run(sha256(token), user.id, Date.now() + 30 * 24 * 60 * 60 * 1000);
  return token;
}
