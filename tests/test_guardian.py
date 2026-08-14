import json
from pathlib import Path

from hermes_windows_guardian.core import Health
from hermes_windows_guardian.guardian import Guardian, GuardianConfig


class FakeProbe:
    def __init__(self, health: Health):
        self.health = health

    def health_snapshot(self):
        return {"health": self.health, "cli": self.health.value, "pids": []}


class FakeRestarter:
    def __init__(self):
        self.calls = 0

    def restart(self, dry_run=False):
        self.calls += 1
        return {"ok": True, "dry_run": dry_run, "method": "fake"}


def cfg(tmp_path: Path) -> GuardianConfig:
    return GuardianConfig(
        state_dir=tmp_path,
        cooldown_seconds=900,
        post_restart_wait_seconds=0,
    )


def test_alive_never_restarts(tmp_path):
    restarter = FakeRestarter()
    result = Guardian(cfg(tmp_path), FakeProbe(Health.ALIVE), restarter).run_once()
    assert result["action"] == "none"
    assert restarter.calls == 0


def test_unknown_fails_safe_without_restart(tmp_path):
    restarter = FakeRestarter()
    result = Guardian(cfg(tmp_path), FakeProbe(Health.UNKNOWN), restarter).run_once()
    assert result["action"] == "inconclusive_no_action"
    assert restarter.calls == 0


def test_dead_restarts_once_then_cooldown_blocks_loop(tmp_path):
    restarter = FakeRestarter()
    guardian = Guardian(cfg(tmp_path), FakeProbe(Health.DEAD), restarter)
    first = guardian.run_once()
    second = guardian.run_once()
    assert first["action"] == "restart_triggered"
    assert second["action"] == "cooldown_no_action"
    assert restarter.calls == 1


def test_disable_flag_prevents_probe_and_restart(tmp_path):
    restarter = FakeRestarter()
    config = cfg(tmp_path)
    config.disable_flag.write_text("maintenance", encoding="utf-8")
    result = Guardian(config, FakeProbe(Health.DEAD), restarter).run_once()
    assert result["action"] == "disabled"
    assert restarter.calls == 0


def test_event_log_contains_no_secrets_or_command_lines(tmp_path):
    restarter = FakeRestarter()
    config = cfg(tmp_path)
    Guardian(config, FakeProbe(Health.ALIVE), restarter).run_once()
    event = json.loads(config.event_log.read_text(encoding="utf-8").splitlines()[-1])
    assert set(event) <= {
        "ts",
        "event",
        "health",
        "pids",
        "action",
        "method",
        "ok",
        "dry_run",
    }
