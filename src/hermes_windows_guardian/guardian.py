from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .core import Health


class Probe(Protocol):
    def health_snapshot(self) -> dict[str, Any]: ...


class Restarter(Protocol):
    def restart(self, dry_run: bool = False) -> dict[str, Any]: ...


def read_operator_intent(state_file: Path) -> str:
    """Return running, stopped, or unknown without guessing operator intent."""
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"

    desired = data.get("desired_state")
    if isinstance(desired, str):
        return desired if desired in {"running", "stopped"} else "unknown"

    runtime = data.get("gateway_state")
    if runtime in {"running", "draining", "degraded"}:
        return "running"
    if runtime == "stopped":
        return "stopped"
    return "unknown"


@dataclass(frozen=True)
class GuardianConfig:
    state_dir: Path
    upstream_state_file: Path
    cooldown_seconds: int = 15 * 60
    post_restart_wait_seconds: int = 20

    @property
    def event_log(self) -> Path:
        return self.state_dir / "events.jsonl"

    @property
    def disable_flag(self) -> Path:
        return self.state_dir / "disabled"


class Guardian:
    def __init__(self, config: GuardianConfig, probe: Probe, restarter: Restarter):
        self.config = config
        self.probe = probe
        self.restarter = restarter

    def _log(self, event: dict[str, Any]) -> None:
        allowed = {
            "event",
            "health",
            "intent",
            "pids",
            "action",
            "method",
            "ok",
            "dry_run",
        }
        clean = {key: value for key, value in event.items() if key in allowed}
        clean["ts"] = datetime.now(UTC).isoformat(timespec="seconds")
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        with self.config.event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(clean, ensure_ascii=False, sort_keys=True) + "\n")

    def _in_cooldown(self) -> bool:
        try:
            lines = self.config.event_log.read_text(encoding="utf-8").splitlines()[-50:]
        except OSError:
            return False
        now = datetime.now(UTC)
        for line in reversed(lines):
            try:
                event = json.loads(line)
                if event.get("event") != "restart_triggered":
                    continue
                at = datetime.fromisoformat(event["ts"])
                return (now - at).total_seconds() < self.config.cooldown_seconds
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return False

    def run_once(self, dry_run: bool = False) -> dict[str, Any]:
        if self.config.disable_flag.exists():
            result = {"action": "disabled"}
            self._log({"event": "disabled", **result})
            return result

        snapshot = self.probe.health_snapshot()
        health = snapshot["health"]
        pids = snapshot.get("pids")
        if health is Health.ALIVE:
            result = {"action": "none", "health": health.value, "pids": pids}
            self._log({"event": "alive", **result})
            return result
        if health is Health.UNKNOWN:
            result = {
                "action": "inconclusive_no_action",
                "health": health.value,
                "pids": pids,
            }
            self._log({"event": "inconclusive", **result})
            return result

        intent = read_operator_intent(self.config.upstream_state_file)
        if intent != "running":
            action = (
                "operator_stop_no_action"
                if intent == "stopped"
                else "intent_unknown_no_action"
            )
            result = {
                "action": action,
                "health": health.value,
                "intent": intent,
                "pids": pids,
            }
            self._log({"event": action, **result})
            return result
        if self._in_cooldown():
            result = {
                "action": "cooldown_no_action",
                "health": health.value,
                "pids": pids,
            }
            self._log({"event": "cooldown", **result})
            return result

        recovery = self.restarter.restart(dry_run=dry_run)
        result = {
            "action": "restart_triggered" if recovery.get("ok") else "restart_failed",
            "health": health.value,
            "pids": pids,
            "method": recovery.get("method"),
            "ok": bool(recovery.get("ok")),
            "dry_run": bool(recovery.get("dry_run")),
        }
        self._log(
            {
                "event": "restart_triggered"
                if recovery.get("ok")
                else "restart_failed",
                **result,
            }
        )
        if (
            recovery.get("ok")
            and not dry_run
            and self.config.post_restart_wait_seconds > 0
        ):
            time.sleep(self.config.post_restart_wait_seconds)
        return result
