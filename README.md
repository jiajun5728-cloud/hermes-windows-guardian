# Hermes Windows Guardian

[![Windows CI](https://github.com/jiajun5728-cloud/hermes-windows-guardian/actions/workflows/test.yml/badge.svg)](https://github.com/jiajun5728-cloud/hermes-windows-guardian/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A conservative, windowless watchdog for the [Hermes Agent](https://github.com/NousResearch/hermes-agent) messaging Gateway on Windows 10/11.

**中文说明见下方。**

## Why

A healthy Desktop window does not always mean the messaging Gateway is alive. Windows users have reported silent exits, Scheduled Task defaults that stop long-running gateways, startup races, console flashes, and orphan-reaper conflicts. Guardian adds an independent, current-user watchdog without modifying Hermes or reading your conversations.

Related public reports include [#35692](https://github.com/NousResearch/hermes-agent/issues/35692), [#41662](https://github.com/NousResearch/hermes-agent/issues/41662), [#48820](https://github.com/NousResearch/hermes-agent/issues/48820), [#83683](https://github.com/NousResearch/hermes-agent/issues/83683), [#84694](https://github.com/NousResearch/hermes-agent/issues/84694), and [#84855](https://github.com/NousResearch/hermes-agent/issues/84855).

## Safety model

Guardian is deliberately conservative:

- it requires **two negative signals** before declaring the Gateway dead;
- an inconclusive check does nothing;
- it never kills a running Gateway;
- recovery has a 15-minute cooldown;
- logs contain status and PIDs only—never command lines, messages, configuration, or environment variables;
- it does not read `.env`, sessions, memories, credentials, or platform tokens;
- it uses `pythonw.exe` and hidden child processes to avoid console flashes.

## Install

Prerequisites: Windows 10/11, Python 3.11+, and a working Hermes Agent installation.

```powershell
pipx install git+https://github.com/jiajun5728-cloud/hermes-windows-guardian.git
```

Or with `uv`:

```powershell
uv tool install git+https://github.com/jiajun5728-cloud/hermes-windows-guardian.git
```

## Use

Read-only health check:

```powershell
hermes-windows-guardian --json check
```

Exercise all decision logic without recovery:

```powershell
hermes-windows-guardian --json run-once --dry-run
```

Install a current-user Scheduled Task that checks every five minutes:

```powershell
hermes-windows-guardian install
```

Pause during maintenance:

```powershell
New-Item "$env:LOCALAPPDATA\hermes-windows-guardian\disabled" -ItemType File -Force
```

Resume:

```powershell
Remove-Item "$env:LOCALAPPDATA\hermes-windows-guardian\disabled"
```

Uninstall the Scheduled Task:

```powershell
hermes-windows-guardian uninstall
```

## How recovery works

1. Ask the official Hermes CLI for Gateway status.
2. Independently inspect Windows process metadata for the exact `python -m hermes_cli.main ... gateway run` runtime.
3. If either signal says alive, do nothing.
4. If inspection fails or disagrees inconclusively, do nothing.
5. Only when both signals are negative, request the official `Hermes_Gateway` Scheduled Task.
6. If that task does not exist, fall back to the official `hermes gateway start` command.

No force-kill path exists in this project.

## Privacy

Guardian is local-only. It makes no network requests. Its JSONL event log is stored at:

```text
%LOCALAPPDATA%\hermes-windows-guardian\events.jsonl
```

See [SECURITY.md](SECURITY.md) for the threat model and reporting process.

## Project status

`v0.1` is an independent community preview tested on Windows 11 with Hermes Agent. It is not affiliated with or endorsed by NousResearch. Upstream behavior changes quickly; please report reproducible failures with secrets removed.

---

# 中文说明

Hermes Windows Guardian 是一个面向 Windows 10/11 的保守型、无黑框 Hermes Gateway 看门狗。

它解决的问题很具体：Desktop 正常打开时，负责飞书、微信、Telegram 等消息通道的 Gateway 仍可能静默退出。Guardian 每五分钟独立检查一次，但只有 **Hermes CLI 和 Windows 进程检查同时确认死亡** 才会尝试恢复。

它不会读取聊天、记忆、`.env`、密钥或平台 Token；不会上传数据；不会杀死正在运行的 Gateway；判断不确定时宁可不动作。

安装：

```powershell
uv tool install git+https://github.com/jiajun5728-cloud/hermes-windows-guardian.git
hermes-windows-guardian --json check
hermes-windows-guardian install
```

本项目采用 MIT 许可证，是独立社区项目，并非 NousResearch 官方组件。
