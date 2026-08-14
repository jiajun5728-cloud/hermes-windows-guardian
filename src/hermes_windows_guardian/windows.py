from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import classify_health, looks_like_gateway

CREATE_NO_WINDOW = 0x08000000


def hidden_process_kwargs() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return {"creationflags": CREATE_NO_WINDOW, "startupinfo": startup}


def default_hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME", "").strip()
    if configured:
        return Path(configured)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def find_hermes_executable(home: Path) -> Path | None:
    candidates = [
        home / "hermes-agent" / "venv" / "Scripts" / "hermes.exe",
        home / "venv" / "Scripts" / "hermes.exe",
    ]
    on_path = shutil.which("hermes")
    if on_path:
        candidates.append(Path(on_path))
    return next((path for path in candidates if path.is_file()), None)


def parse_cli_status(output: str) -> str:
    lowered = output.lower()
    if "no gateway process detected" in lowered or "not running" in lowered:
        return "dead"
    if (
        "gateway service is running" in lowered
        or "gateway is running" in lowered
        or "gateway process running" in lowered
    ):
        return "alive"
    if any(
        line.strip().lower().startswith("pid:") and any(ch.isdigit() for ch in line)
        for line in output.splitlines()
    ):
        return "alive"
    return "unknown"


class WindowsProbe:
    def __init__(self, home: Path | None = None, timeout: int = 30):
        self.home = home or default_hermes_home()
        self.timeout = timeout

    def cli_status(self) -> str:
        executable = find_hermes_executable(self.home)
        if executable is None:
            return "unknown"
        try:
            result = subprocess.run(
                [str(executable), "gateway", "status"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env={**os.environ, "HERMES_HOME": str(self.home)},
                **hidden_process_kwargs(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"
        return parse_cli_status((result.stdout or "") + "\n" + (result.stderr or ""))

    def gateway_pids(self) -> list[int] | None:
        if sys.platform != "win32":
            return None
        script = (
            "$ErrorActionPreference='Stop';"
            "$rows=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
            "$_.CommandLine -match '(?i)(^|\\s)-m\\s+hermes_cli\\.main(\\s|$)' -and "
            "$_.CommandLine -match '(?i)(^|\\s)gateway\\s+run(\\s|$)' } | "
            "Select-Object ProcessId,CommandLine;"
            "$rows | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                **hidden_process_kwargs(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        raw = (result.stdout or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        rows = data if isinstance(data, list) else [data]
        pids: list[int] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            command = str(row.get("CommandLine") or "")
            try:
                pid = int(row.get("ProcessId") or 0)
            except (TypeError, ValueError):
                continue
            if pid > 0 and looks_like_gateway(command):
                pids.append(pid)
        return sorted(set(pids))

    def health_snapshot(self) -> dict[str, Any]:
        cli = self.cli_status()
        pids = self.gateway_pids()
        return {"health": classify_health(cli, pids), "cli": cli, "pids": pids}


class WindowsRestarter:
    def __init__(
        self, home: Path | None = None, profile: str | None = None, timeout: int = 30
    ):
        self.home = home or default_hermes_home()
        self.profile = profile
        self.timeout = timeout

    @property
    def task_name(self) -> str:
        return (
            "Hermes_Gateway" if not self.profile else f"Hermes_Gateway_{self.profile}"
        )

    def restart(self, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"ok": True, "dry_run": True, "method": "scheduled_task"}
        try:
            result = subprocess.run(
                ["schtasks.exe", "/Run", "/TN", self.task_name],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                **hidden_process_kwargs(),
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            return {"ok": True, "dry_run": False, "method": "scheduled_task"}

        executable = find_hermes_executable(self.home)
        if executable is None:
            return {"ok": False, "dry_run": False, "method": "hermes_cli_start"}
        command = [str(executable)]
        if self.profile:
            command.extend(["--profile", self.profile])
        command.extend(["gateway", "start"])
        try:
            fallback = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env={**os.environ, "HERMES_HOME": str(self.home)},
                **hidden_process_kwargs(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"ok": False, "dry_run": False, "method": "hermes_cli_start"}
        return {
            "ok": fallback.returncode == 0,
            "dry_run": False,
            "method": "hermes_cli_start",
        }


def build_watchdog_task_command(
    pythonw: str,
    task_name: str = "Hermes Windows Guardian",
    interval_minutes: int = 5,
    run_once_args: list[str] | None = None,
) -> list[str]:
    action_parts = [pythonw, "-m", "hermes_windows_guardian.cli"]
    action_parts.extend(run_once_args or [])
    action_parts.append("run-once")
    action = subprocess.list2cmdline(action_parts)
    return [
        shutil.which("schtasks.exe") or "schtasks.exe",
        "/Create",
        "/TN",
        task_name,
        "/SC",
        "MINUTE",
        "/MO",
        str(interval_minutes),
        "/TR",
        action,
        "/RL",
        "LIMITED",
        "/F",
    ]
