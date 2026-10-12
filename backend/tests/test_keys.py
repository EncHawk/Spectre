from __future__ import annotations

from healer.keys import generate_key, hash_key, mask, parse_prefix, verify_key


def test_key_format_and_digest():
    key, prefix, digest = generate_key()
    assert len(key) == 56
    assert key.startswith(f"spk_{prefix}_")
    assert parse_prefix(key) == prefix
    assert mask(key) == f"spk_{prefix}_…"
    assert digest == hash_key(key)
    assert verify_key(key, digest)
    assert not verify_key(key[:-1] + ("A" if key[-1] != "A" else "B"), digest)
    assert not verify_key("not-a-key", digest)


def test_generated_keys_are_distinct():
    assert generate_key()[0] != generate_key()[0]
