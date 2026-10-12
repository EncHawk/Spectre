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
    def do_GET(self):
        assert self.headers["Authorization"] == "Bearer test-service-token"
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
        if self.path == "/v1/example-runs":
            assert body == {"example": "checkout_support"}
            self.send_json({"example": "checkout_support", "before_passed": 1, "after_passed": 3})
        elif self.path == "/v1/proposals":
            assert body["user_id"] == "google-sub-1" and body["repository"] == "example/agent"
            assert body["finding_id"] == "a" * 16
            self.send_json({"proposal": {"status": "proposed", "summary": "draft", "diff": "diff"}, "validation": "not_run", "pull_request": None})
        else:
            self.send_error(404)

    def send_json(self, value):
        body = json.dumps(value).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
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

            for _ in range(100):
                try:
                    assert request("/api/me")[0] == 401
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            else: raise AssertionError("Next server did not start")
            assert request("/api/auth/google/start")[0] == 503
            token = "integration-session"
            # A cookie-bearing request initializes the control-plane schema.
            assert request("/api/me", token=token)[0] == 401
            with sqlite3.connect(database) as db:
                db.execute("INSERT INTO users VALUES(?,?,?)", ("google-sub-1", "dev@example.com", "Developer"))
                db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), "google-sub-1", int(time.time() * 1000) + 60000))
                db.execute("INSERT INTO repositories(user_id,full_name,default_branch,commit_sha,file_count,indexed_at,files_json) VALUES(?,?,?,?,?,?,?)",
                           ("google-sub-1", "example/agent", "main", "b" * 40, 1, "2026-10-12T00:00:00Z", '[{"path":"agent.py","size":12}]'))
            assert request("/api/me", token=token)[1]["user"]["email"] == "dev@example.com"
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
            print("Smoke passed: session auth, CSRF, agent ownership, Doctor, example run, draft proposal, repository snapshot")
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
            backend.shutdown()


if __name__ == "__main__":
    run()
