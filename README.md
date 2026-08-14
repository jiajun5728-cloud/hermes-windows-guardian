# Hermes Windows Guardian

[![Windows CI](https://github.com/lajiaojiang-ai/hermes-windows-guardian/actions/workflows/test.yml/badge.svg)](https://github.com/lajiaojiang-ai/hermes-windows-guardian/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A conservative, windowless watchdog for the [Hermes Agent](https://github.com/NousResearch/hermes-agent) messaging Gateway on Windows 10/11.

**中文说明见下方。**

## Why

A healthy Desktop window does not always mean the messaging Gateway is alive. Windows users have reported silent exits, startup races, and orphan-reaper conflicts. Hermes already includes Windows launch helpers, Scheduled Task restart settings, and an in-process `gateway.loop_watchdog`; Guardian is an additional current-user, out-of-process fallback for installations where failures still escape those layers.

Related public reports include [#35692](https://github.com/NousResearch/hermes-agent/issues/35692), [#41662](https://github.com/NousResearch/hermes-agent/issues/41662), [#48820](https://github.com/NousResearch/hermes-agent/issues/48820), [#83683](https://github.com/NousResearch/hermes-agent/issues/83683), [#84694](https://github.com/NousResearch/hermes-agent/issues/84694), and [#84855](https://github.com/NousResearch/hermes-agent/issues/84855).

## Safety model

Guardian is deliberately conservative:

- it requires **two negative signals** before declaring the Gateway dead;
- it recovers only when `gateway_state.json` still records an explicit running intent;
- an intentional `hermes gateway stop`, missing state, or unreadable state blocks recovery;
- an inconclusive check does nothing;
- it never kills a running Gateway;
- recovery has a 15-minute cooldown;
- logs contain status and PIDs only—never command lines, messages, configuration, or environment variables;
- it does not read `.env`, sessions, memories, credentials, or platform tokens;
- it uses `pythonw.exe` and hidden child processes to avoid console flashes.

## Install

Prerequisites: Windows 10/11, Python 3.11+, and a working Hermes Agent installation.

```powershell
pipx install git+https://github.com/lajiaojiang-ai/hermes-windows-guardian.git
```

Or with `uv`:

```powershell
uv tool install git+https://github.com/lajiaojiang-ai/hermes-windows-guardian.git
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
5. Read Hermes' persisted operator intent; stop if it is not explicitly `running`.
6. Only when both health signals are negative and intent is running, request the official `Hermes_Gateway` Scheduled Task.
7. If that task does not exist, fall back to the official `hermes gateway start` command.

No force-kill path exists in this project.

## Upstream context and known limits

- This is a community fallback, **not** an official Hermes component and not a replacement for `hermes gateway install`.
- It may restart a Gateway after a Desktop orphan-reaper event; it cannot prevent or repair the Desktop reaper itself ([#83683](https://github.com/NousResearch/hermes-agent/issues/83683), [#84855](https://github.com/NousResearch/hermes-agent/issues/84855)).
- It does not fix messaging-adapter configuration, proxy behavior, or unexplained hard-exit root causes.
- `v0.1` supervises the default profile only. Multi-profile process attribution is intentionally out of scope.
- Upstream supervision is evolving ([#31485](https://github.com/NousResearch/hermes-agent/issues/31485), [#41761](https://github.com/NousResearch/hermes-agent/pull/41761)). If official out-of-process supervision covers this gap, this project should become thinner or retire rather than compete with it.

## Privacy

Guardian is local-only. It makes no network requests. Its JSONL event log is stored at:

```text
%LOCALAPPDATA%\hermes-windows-guardian\events.jsonl
```

See [SECURITY.md](SECURITY.md) for the threat model and reporting process.

## Project status

`v0.1` is an independent community preview tested on Windows 11 with Hermes Agent v0.20.0 (2026.8.3). It is not affiliated with or endorsed by NousResearch. Upstream behavior changes quickly; please report reproducible failures with secrets removed.

---

# 中文说明

Hermes Windows Guardian 是一个面向 Windows 10/11 的保守型、无黑框 Hermes Gateway 看门狗。

它解决的问题很具体：Desktop 正常打开时，负责消息通道的 Gateway 仍可能静默退出。Hermes 上游已经有 Windows 启动脚本、计划任务重启设置和进程内 `gateway.loop_watchdog`；Guardian 只是这些机制仍未兜住时的额外进程外保险。

Guardian 每五分钟独立检查一次，但只有 **Hermes CLI 和 Windows 进程检查同时确认死亡**，并且 `gateway_state.json` 仍明确记录运行意图时，才会尝试恢复。主动执行 `hermes gateway stop`、状态缺失或状态损坏都会阻止回拉。

它不会读取聊天、记忆、`.env`、密钥或平台 Token；不会上传数据；不会杀死正在运行的 Gateway；判断不确定时宁可不动作。它只能事后回拉，不能阻止 Desktop 误杀，不能修消息适配器、代理或静默硬退出的根因。`v0.1` 只支持默认 profile。

安装：

```powershell
uv tool install git+https://github.com/lajiaojiang-ai/hermes-windows-guardian.git
hermes-windows-guardian --json check
hermes-windows-guardian install
```

本项目采用 MIT 许可证，是独立社区项目，并非 NousResearch 官方组件。
