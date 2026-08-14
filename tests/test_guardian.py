import json
from pathlib import Path

from hermes_windows_guardian.core import Health
from hermes_windows_guardian.guardian import (
    Guardian,
    GuardianConfig,
    read_operator_intent,
)


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
    upstream_state = tmp_path / "gateway_state.json"
    upstream_state.write_text(
        json.dumps({"gateway_state": "running"}), encoding="utf-8"
    )
    return GuardianConfig(
        state_dir=tmp_path,
        upstream_state_file=upstream_state,
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


def test_explicit_stopped_intent_blocks_recovery(tmp_path):
    restarter = FakeRestarter()
    config = cfg(tmp_path)
    config.upstream_state_file.write_text(
        json.dumps({"gateway_state": "running", "desired_state": "stopped"}),
        encoding="utf-8",
    )
    result = Guardian(config, FakeProbe(Health.DEAD), restarter).run_once()
    assert result["action"] == "operator_stop_no_action"
    assert restarter.calls == 0


def test_missing_or_corrupt_intent_fails_safe(tmp_path):
    for index, raw in enumerate((None, "not-json")):
        case = tmp_path / str(index)
        case.mkdir()
        config = cfg(case)
        if raw is None:
            config.upstream_state_file.unlink()
        else:
            config.upstream_state_file.write_text(raw, encoding="utf-8")
        restarter = FakeRestarter()
        result = Guardian(config, FakeProbe(Health.DEAD), restarter).run_once()
        assert result["action"] == "intent_unknown_no_action"
        assert restarter.calls == 0


def test_intent_reader_honors_explicit_desired_state(tmp_path):
    state = tmp_path / "gateway_state.json"
    state.write_text(
        json.dumps({"gateway_state": "stopped", "desired_state": "running"}),
        encoding="utf-8",
    )
    assert read_operator_intent(state) == "running"
    state.write_text(
        json.dumps({"gateway_state": "running", "desired_state": "stopped"}),
        encoding="utf-8",
    )
    assert read_operator_intent(state) == "stopped"


def test_legacy_transient_running_state_allows_recovery(tmp_path):
    state = tmp_path / "gateway_state.json"
    for value in ("running", "draining", "degraded"):
        state.write_text(json.dumps({"gateway_state": value}), encoding="utf-8")
        assert read_operator_intent(state) == "running"


def test_event_log_contains_no_secrets_or_command_lines(tmp_path):
    restarter = FakeRestarter()
    config = cfg(tmp_path)
    Guardian(config, FakeProbe(Health.ALIVE), restarter).run_once()
    event = json.loads(config.event_log.read_text(encoding="utf-8").splitlines()[-1])
    assert set(event) <= {
        "ts",
        "event",
        "health",
        "intent",
        "pids",
        "action",
        "method",
        "ok",
        "dry_run",
    }
