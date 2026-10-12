from healer.privacy import Redactor


def test_redacts_nested_secrets_and_pii():
    value = {
        "password": "hunter2",
        "note": "email me at person@example.com with token=abc123",
        "nested": [{"Authorization": "Bearer secret"}],
    }
    redacted = Redactor().redact(value)
    assert redacted["password"] == "[REDACTED:secret]"
    assert "person@example.com" not in redacted["note"]
    assert "abc123" not in redacted["note"]
    assert redacted["nested"][0]["Authorization"] == "[REDACTED:secret]"


def test_redacts_aws_key_and_card():
    fake_aws_key = "AKIA" + ("A" * 16)
    text = f"key {fake_aws_key} card 4111 1111 1111 1111"
    result = Redactor().redact_text(text)
    assert fake_aws_key not in result
    assert "4111" not in result
