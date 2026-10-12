"""Local integration smoke test; requires `npm run build` first."""

import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Doctor(BaseHTTPRequestHandler):
    project_id = "11111111-1111-4111-8111-111111111111"
    key_id = "22222222-2222-4222-8222-222222222222"
    key_value = "spk_deadbeef_" + "A" * 43
    revoked = False
    key_created = False

    def do_GET(self):
        assert self.headers["Authorization"] == "Bearer test-service-token"
        if self.path == "/internal/access":
            assert self.headers["X-Spectre-User-Id"] == "google-sub-1"
            self.send_json({"has_active_key": self.key_created and not self.revoked})
            return
        if self.path.startswith("/internal/projects"):
            assert self.headers["X-Spectre-User-Id"] == "google-sub-1"
            if self.path.endswith("/keys"):
                self.send_json({"keys": [{"id": self.key_id, "prefix": "deadbeef", "scopes": ["runs:read"], "last_used_at": None, "revoked_at": "now" if self.revoked else None}]})
            else:
                self.send_json({"projects": [{"id": self.project_id, "app_id": "orders", "name": "Orders"}]})
            return
        if self.path == "/v1/examples":
            self.send_json({"examples": [{"id": "checkout_support", "title": "Checkout support team", "steps": ["route", "verify"], "cases": ["normal"]}]})
            return
        assert "app_id=orders" in self.path
        assert "user_id=google-sub-1" in self.path
        assert "repository=example%2Fagent" in self.path
        value = {
            "generated_at": "2026-10-12T00:00:00Z", "repository": {"github_url": "https://github.com/example/agent"},
            "trace_count": 2, "finding_count": 1,
            "runs": [{"trace_id": "trace-1", "session_id": "chat-1", "name": "orders", "status": "error", "source": "local", "started_at": "2026-10-12T00:00:00Z", "trace_url": None, "spans_truncated": False, "spans": []}],
            "rows": [{"finding": {"id": "a" * 16, "reason": "Tool failed without recovery", "severity": "high",
                                  "trace_id": "trace-1", "trace_url": None}, "session_id": "chat-1",
                      "suggestion": "Add a tested retry", "candidate_locations": [], "resolution": None, "copy_to_agent": "old"}],
        }
        self.send_json(value)

    def do_POST(self):
        assert self.headers["Authorization"] == "Bearer test-service-token"
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.startswith("/internal/projects"):
            assert self.headers["X-Spectre-User-Id"] == "google-sub-1"
            if self.path.endswith("/keys"):
                assert body == {"scopes": ["runs:read"]}
                Doctor.key_created = True
                self.send_json({"api_key": {"id": self.key_id, "prefix": "deadbeef", "key": self.key_value, "scopes": ["runs:read"]}}, status=201)
            else:
                assert body == {"app_id": "orders", "name": "Orders"}
                self.send_json({"project": {"id": self.project_id, **body}}, status=201)
        elif self.path == "/v1/example-runs":
            assert body == {"example": "checkout_support"}
            self.send_json({"example": "checkout_support", "before_passed": 1, "after_passed": 3})
        elif self.path == "/v1/proposals":
            assert body["user_id"] == "google-sub-1" and body["repository"] == "example/agent"
            assert body["finding_id"] == "a" * 16
            self.send_json({"proposal": {"status": "proposed", "summary": "draft", "diff": "diff"}, "validation": "not_run", "pull_request": None})
        elif self.path == "/v1/investigations":
            assert body["user_id"] == "google-sub-1" and body["repository"] == "example/agent"
            assert body["finding_id"] == "a" * 16 and body["app_id"] == "orders"
            self.send_json({"evidence": {"finding_id": "a" * 16, "trace_id": "trace-1", "check": "ignored_error", "reason": "Tool failed", "invocation_path": ["orders", "gateway"]}, "likely_cause": "Gateway timeout was ignored", "suggested_fix": "Gate success on confirmation", "how_to_verify": "Replay timeout", "model_status": "not_configured", "basis": "Observed trace finding"})
        else:
            self.send_error(404)

    def do_DELETE(self):
        assert self.headers["Authorization"] == "Bearer test-service-token"
        assert self.headers["X-Spectre-User-Id"] == "google-sub-1"
        assert self.path.endswith("/keys/" + self.key_id)
        Doctor.revoked = True
        self.send_json({"revoked": True})

    def send_json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, *_):
        pass


def run():
    app_port, api_port = free_port(), free_port()
    base = f"http://127.0.0.1:{app_port}"
    backend = ThreadingHTTPServer(("127.0.0.1", api_port), Doctor)
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "control.sqlite"
        env = dict(os.environ, SPECTRE_PUBLIC_URL=base, SPECTRE_DB_PATH=str(database),
                   SPECTRE_ENCRYPTION_KEY="ab" * 32, HEALER_API_URL=f"http://127.0.0.1:{api_port}",
                   SPECTRE_ALLOWED_EMAIL="dev@example.com",
                   HEALER_SERVER_TOKEN="test-service-token")
        process = subprocess.Popen(["npm", "run", "start", "--", "-p", str(app_port)], cwd=ROOT,
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            def request(path, method="GET", body=None, token=None, origin=None):
                headers = {}
                if token: headers["Cookie"] = f"spectre_session={token}"
                if origin: headers["Origin"] = origin
                if body is not None: headers["Content-Type"] = "application/json"
                req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                             headers=headers, method=method)
                try:
                    with urllib.request.urlopen(req, timeout=3) as response:
                        return response.status, json.loads(response.read())
                except urllib.error.HTTPError as error:
                    raw = error.read()
                    try: return error.code, json.loads(raw)
                    except json.JSONDecodeError: return error.code, {"raw": raw.decode(errors="replace")[:300]}

            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *_):
                    return None

            opener = urllib.request.build_opener(NoRedirect)

            def page(path, token=None):
                headers = {"Cookie": f"spectre_session={token}"} if token else {}
                req = urllib.request.Request(base + path, headers=headers)
                try:
                    with opener.open(req, timeout=3) as response:
                        return response.status, response.headers.get("Location"), response.read().decode(errors="replace")
                except urllib.error.HTTPError as error:
                    return error.code, error.headers.get("Location"), error.read().decode(errors="replace")

            for _ in range(100):
                try:
                    assert request("/api/me")[0] == 401
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            else: raise AssertionError("Next server did not start")
            assert request("/api/auth/google/start")[0] == 503
            assert 'href="/api/auth/google/start"' in page("/")[2]
            assert page("/app")[:2] == (307, "/")
            assert page("/setup")[:2] == (307, "/")
            token = "integration-session"
            # A cookie-bearing request initializes the control-plane schema.
            assert request("/api/me", token=token)[0] == 401
            with sqlite3.connect(database) as db:
                db.execute("INSERT INTO users VALUES(?,?,?)", ("google-sub-1", "dev@example.com", "Developer"))
                db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), "google-sub-1", int(time.time() * 1000) + 60000))
                db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(b"expired-session").hexdigest(), "google-sub-1", int(time.time() * 1000) - 1))
                db.execute("INSERT INTO repositories(user_id,full_name,default_branch,commit_sha,file_count,indexed_at,files_json) VALUES(?,?,?,?,?,?,?)",
                           ("google-sub-1", "example/agent", "main", "b" * 40, 1, "2026-10-12T00:00:00Z", '[{"path":"agent.py","size":12}]'))
            assert request("/api/me", token=token)[1]["user"]["email"] == "dev@example.com"
            assert page("/app", "expired-session")[:2] == (307, "/")
            assert page("/app", token)[:2] == (307, "/setup")
            assert page("/app/investigation", token)[:2] == (307, "/setup")
            assert page("/setup", token)[0] == 200
            assert request("/api/projects")[0] == 401
            assert request("/api/projects", method="POST", body={"app_id": "orders", "name": "Orders"}, origin=base)[0] == 401
            assert request("/api/projects", method="POST", body={"app_id": "orders", "name": "Orders"}, token="expired-session", origin=base)[0] == 401
            assert request("/api/projects", method="POST", body={"app_id": "orders", "name": "Orders"}, token=token, origin="http://evil.example")[0] == 403
            assert request("/api/projects", method="POST", body={"app_id": "orders", "name": "Orders"}, token=token, origin=base)[0] == 201
            assert request("/api/projects", token=token)[1]["projects"][0]["app_id"] == "orders"
            key_path = "/api/projects/" + Doctor.project_id + "/keys"
            assert request(key_path, method="POST", body={"scopes": ["runs:read"]}, origin=base)[0] == 401
            assert request(key_path, method="POST", body={"scopes": ["runs:read"]}, token=token, origin="http://evil.example")[0] == 403
            created = request(key_path, method="POST", body={"scopes": ["runs:read"]}, token=token, origin=base)
            assert created[0] == 201 and created[1]["api_key"]["key"] == Doctor.key_value
            assert page("/app", token)[0] == 200
            assert page("/app/investigation", token)[0] == 200
            assert "key" not in request(key_path, token=token)[1]["keys"][0]
            assert request(key_path + "/" + Doctor.key_id, method="DELETE", token=token, origin=base)[1]["revoked"]
            assert request(key_path, token=token)[1]["keys"][0]["revoked_at"]
            assert page("/app", token)[:2] == (307, "/setup")
            csrf = request("/api/agents", method="POST", token=token, origin="http://evil.example",
                           body={"app_id": "orders", "name": "Orders"})
            assert csrf[0] == 403, csrf
            assert request("/api/agents", method="POST", token=token, origin=base,
                           body={"app_id": "orders", "name": "Orders", "description": "Recover failed orders", "repository_id": 1})[0] == 201
            assert request("/api/agents", token=token)[1]["agents"][0]["repository_name"] == "example/agent"
            status, report = request("/api/doctor?app_id=orders", token=token)
            assert status == 200 and report["trace_count"] == 2 and report["finding_count"] == 1
            assert report["runs"][0]["trace_id"] == "trace-1"
            assert "Recover failed orders" in report["rows"][0]["copy_to_agent"]
            assert request("/api/doctor?app_id=other", token=token)[0] == 404
            assert request("/api/repositories", token=token)[1]["repositories"][0]["file_count"] == 1
            assert request("/api/examples")[0] == 401
            assert request("/api/examples", token=token)[1]["examples"][0]["id"] == "checkout_support"
            assert request("/api/example-runs", method="POST", token=token, origin="http://evil.example", body={"example": "checkout_support"})[0] == 403
            assert request("/api/example-runs", method="POST", token=token, origin=base, body={"example": "checkout_support"})[1]["after_passed"] == 3
            assert request("/api/proposals", method="POST", token=token, origin=base, body={"app_id": "other", "finding_id": "a" * 16})[0] == 400
            assert request("/api/proposals", method="POST", token=token, origin=base, body={"app_id": "orders", "finding_id": "a" * 16})[1]["validation"] == "not_run"
            assert request("/api/investigations", method="POST", token=token, origin="http://evil.example", body={"app_id": "orders", "finding_id": "a" * 16})[0] == 403
            assert request("/api/investigations", method="POST", token=token, origin=base, body={"app_id": "other", "finding_id": "a" * 16})[0] == 400
            assert request("/api/investigations", method="POST", token=token, origin=base, body={"app_id": "orders", "finding_id": "a" * 16})[1]["suggested_fix"] == "Gate success on confirmation"
            print("Smoke passed: session auth, CSRF, key creation/revocation, Doctor, example run, investigation, repository snapshot")
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
            backend.shutdown()


if __name__ == "__main__":
    run()
