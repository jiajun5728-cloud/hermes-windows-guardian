from hermes_windows_guardian.core import (
    Health,
    classify_health,
    looks_like_gateway,
    redact_text,
)


def test_strict_gateway_command_matcher_accepts_runtime_only():
    assert looks_like_gateway(
        ["pythonw.exe", "-m", "hermes_cli.main", "gateway", "run"]
    )
    assert looks_like_gateway(
        [
            "python.exe",
            "-m",
            "hermes_cli.main",
            "--profile",
            "work",
            "gateway",
            "run",
            "--replace",
        ]
    )
    assert not looks_like_gateway(
        ["python.exe", "-m", "hermes_cli.main", "gateway", "status"]
    )
    assert not looks_like_gateway(["python.exe", "-c", "print('gateway run')"])


def test_health_requires_two_negative_signals_before_dead():
    assert classify_health("alive", [111]) is Health.ALIVE
    assert classify_health("dead", [111]) is Health.ALIVE
    assert classify_health("unknown", [111]) is Health.ALIVE
    assert classify_health("dead", []) is Health.DEAD
    assert classify_health("unknown", []) is Health.UNKNOWN


def test_redaction_removes_home_and_user_profile():
    text = r"C:\Users\example-user\AppData\Local\hermes\logs\gateway.log"
    redacted = redact_text(text, [r"C:\Users\example-user"])
    assert "example-user" not in redacted.lower()
    assert redacted.startswith("<redacted-home>")
