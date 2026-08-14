from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .guardian import Guardian, GuardianConfig
from .windows import (
    WindowsProbe,
    WindowsRestarter,
    build_watchdog_task_command,
    default_hermes_home,
    hidden_process_kwargs,
)

TASK_NAME = "Hermes Windows Guardian"


def default_state_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA", "").strip()
    return (Path(local) if local else Path.home()) / "hermes-windows-guardian"


def build_guardian(args: argparse.Namespace) -> Guardian:
    home = Path(args.home) if args.home else default_hermes_home()
    config = GuardianConfig(
        state_dir=Path(args.state_dir) if args.state_dir else default_state_dir(),
        upstream_state_file=home / "gateway_state.json",
        cooldown_seconds=args.cooldown,
        post_restart_wait_seconds=args.post_restart_wait,
    )
    return Guardian(config, WindowsProbe(home), WindowsRestarter(home))


def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(" ".join(f"{key}={value}" for key, value in payload.items()))


def scheduled_run_args(args: argparse.Namespace) -> list[str]:
    result: list[str] = []
    if args.home:
        result.extend(["--home", args.home])
    if args.state_dir:
        result.extend(["--state-dir", args.state_dir])
    result.extend(["--cooldown", str(args.cooldown)])
    result.extend(["--post-restart-wait", str(args.post_restart_wait)])
    return result


def install_task(interval: int, run_once_args: list[str] | None = None) -> dict:
    if sys.platform != "win32":
        return {"ok": False, "error": "Windows only"}
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    command = build_watchdog_task_command(
        pythonw, TASK_NAME, interval, run_once_args=run_once_args
    )
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        **hidden_process_kwargs(),
    )
    return {
        "ok": result.returncode == 0,
        "task": TASK_NAME,
        "interval_minutes": interval,
    }


def uninstall_task() -> dict:
    if sys.platform != "win32":
        return {"ok": False, "error": "Windows only"}
    result = subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        **hidden_process_kwargs(),
    )
    return {"ok": result.returncode == 0, "task": TASK_NAME}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Conservative Windows watchdog for Hermes Agent Gateway"
    )
    root.add_argument(
        "--home", help="Hermes home (defaults to HERMES_HOME or %LOCALAPPDATA%\\hermes)"
    )
    root.add_argument("--state-dir", help="Guardian state directory")

    root.add_argument("--cooldown", type=int, default=900)
    root.add_argument("--post-restart-wait", type=int, default=20)
    root.add_argument("--json", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Read-only health check")
    run = commands.add_parser(
        "run-once", help="Check once and recover only after confirmed death"
    )
    run.add_argument("--dry-run", action="store_true")
    install = commands.add_parser(
        "install", help="Install a five-minute current-user Scheduled Task"
    )
    install.add_argument("--interval", type=int, default=5)
    commands.add_parser("uninstall", help="Remove the Guardian Scheduled Task")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "install":
        result = install_task(args.interval, scheduled_run_args(args))
    elif args.command == "uninstall":
        result = uninstall_task()
    elif args.command == "check":
        snapshot = build_guardian(args).probe.health_snapshot()
        result = {**snapshot, "health": snapshot["health"].value}
    else:
        result = build_guardian(args).run_once(dry_run=args.dry_run)
    emit(result, args.json)
    return 0 if result.get("ok", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
