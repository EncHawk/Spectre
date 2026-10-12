"""Pinned, per-user GitHub checkouts for Doctor; OAuth tokens are never persisted."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path

_LOCK = threading.Lock()
_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_SHA = re.compile(r"[a-f0-9]{40}\Z")


class RepositoryRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = self.root / "registry.sqlite"
        with sqlite3.connect(self.registry) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS checkouts (
                user_id TEXT NOT NULL, full_name TEXT NOT NULL, commit_sha TEXT NOT NULL,
                path TEXT NOT NULL, PRIMARY KEY(user_id, full_name, commit_sha))""")

    def path_for(self, user_id: str, full_name: str, commit_sha: str) -> Path | None:
        if not self._valid(user_id, full_name, commit_sha):
            return None
        with sqlite3.connect(self.registry) as db:
            row = db.execute(
                "SELECT path FROM checkouts WHERE user_id=? AND full_name=? AND commit_sha=?",
                (user_id, full_name, commit_sha),
            ).fetchone()
        if not row:
            return None
        path = Path(row[0]).resolve()
        return path if path.is_relative_to(self.root) and path.is_dir() else None

    def ingest(self, *, user_id: str, full_name: str, commit_sha: str, token: str) -> dict:
        if not self._valid(user_id, full_name, commit_sha):
            raise ValueError("invalid repository identity")
        if not token or len(token) > 4096:
            raise ValueError("invalid GitHub access token")
        with _LOCK:
            existing = self.path_for(user_id, full_name, commit_sha)
            if existing:
                return self._result(full_name, commit_sha, existing)
            digest = hashlib.sha256(f"{user_id}\0{full_name}\0{commit_sha}".encode()).hexdigest()
            target = self.root / digest
            temporary = Path(tempfile.mkdtemp(prefix="checkout-", dir=self.root))
            try:
                url = f"https://github.com/{full_name}.git"
                basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
                env = dict(
                    os.environ,
                    GIT_TERMINAL_PROMPT="0",
                    GIT_CONFIG_COUNT="1",
                    GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                    GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {basic}",
                )
                commands = [
                    ["git", "init", "--quiet", str(temporary)],
                    ["git", "-C", str(temporary), "remote", "add", "origin", url],
                    [
                        "git",
                        "-C",
                        str(temporary),
                        "fetch",
                        "--quiet",
                        "--depth=1",
                        "origin",
                        commit_sha,
                    ],
                    ["git", "-C", str(temporary), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
                ]
                for command in commands:
                    result = subprocess.run(
                        command, env=env, capture_output=True, timeout=120, check=False
                    )
                    if result.returncode != 0:
                        raise ValueError(
                            "GitHub checkout failed; check repository access and pinned commit"
                        )
                if target.exists():
                    shutil.rmtree(target)
                temporary.rename(target)
                with sqlite3.connect(self.registry) as db:
                    db.execute(
                        "INSERT INTO checkouts VALUES(?,?,?,?)",
                        (user_id, full_name, commit_sha, str(target)),
                    )
                return self._result(full_name, commit_sha, target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)

    @staticmethod
    def _valid(user_id: str, full_name: str, commit_sha: str) -> bool:
        return bool(
            user_id
            and len(user_id) <= 255
            and _NAME.fullmatch(full_name)
            and _SHA.fullmatch(commit_sha)
        )

    @staticmethod
    def _result(full_name: str, commit_sha: str, path: Path) -> dict:
        return {
            "full_name": full_name,
            "commit_sha": commit_sha,
            "path": str(path),
            "indexed": True,
        }
