"""Opaque project API keys. Plaintext is returned only by generate_key()."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

SCOPES = frozenset({"runs:write", "runs:read", "jobs:pull"})
_KEY = re.compile(r"^spk_([0-9a-f]{8})_([A-Za-z0-9_-]{43})$")


def generate_key() -> tuple[str, str, str]:
    prefix = secrets.token_hex(4)
    key = f"spk_{prefix}_{secrets.token_urlsafe(32)}"
    return key, prefix, hash_key(key)


def parse_prefix(key: str) -> str | None:
    match = _KEY.fullmatch(key)
    return match.group(1) if match else None


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def verify_key(key: str, expected_hash: str) -> bool:
    return bool(parse_prefix(key)) and hmac.compare_digest(hash_key(key), expected_hash)


def mask(key: str) -> str:
    prefix = parse_prefix(key)
    return f"spk_{prefix}_…" if prefix else "[invalid key]"
