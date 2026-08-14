from pathlib import Path
from types import SimpleNamespace

from hermes_windows_guardian import windows
from hermes_windows_guardian.windows import (
    WindowsRestarter,
    build_watchdog_task_command,
    parse_cli_status,
)


def test_current_hermes_windows_status_text_is_alive():
    output = "✓ Windows login item installed: C:\\Users\\example\\Startup\\Hermes_Gateway.vbs\n✓ Gateway process running (PID: 38640)"
    assert parse_cli_status(output) == "alive"


def test_task_command_uses_pythonw_and_current_user_task():
    cmd = build_watchdog_task_command(
        pythonw=r"C:\Program Files\Python\pythonw.exe",
        task_name="Hermes Windows Guardian",
        interval_minutes=5,
    )
    joined = " ".join(cmd)
    assert cmd[0].lower().endswith("schtasks.exe")
    assert "/SC" in cmd and "MINUTE" in cmd
    assert "/MO" in cmd and "5" in cmd
    assert "pythonw.exe" in joined
    assert "/RL" in cmd and "LIMITED" in cmd
    assert "/F" in cmd


def test_task_command_persists_custom_home_and_state_dir():
    cmd = build_watchdog_task_command(
        pythonw=r"C:\Program Files\Python\pythonw.exe",
        run_once_args=[
            "--home",
            r"D:\Hermes Home",
            "--state-dir",
            r"D:\Guardian State",
        ],
    )
    action = cmd[cmd.index("/TR") + 1]
    assert '"D:\\Hermes Home"' in action
    assert '"D:\\Guardian State"' in action
    assert action.endswith("run-once")


def test_restarter_falls_back_to_official_cli_when_task_is_absent(
    monkeypatch, tmp_path
):
    executable = tmp_path / "hermes.exe"
    executable.write_text("placeholder", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1 if len(calls) == 1 else 0)

    monkeypatch.setattr(windows.subprocess, "run", fake_run)
    monkeypatch.setattr(windows, "find_hermes_executable", lambda home: executable)

    result = WindowsRestarter(Path(tmp_path)).restart()

    assert result == {"ok": True, "dry_run": False, "method": "hermes_cli_start"}
    assert calls[0][:3] == ["schtasks.exe", "/Run", "/TN"]
    assert calls[1] == [str(executable), "gateway", "start"]
