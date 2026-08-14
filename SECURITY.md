# Security and privacy

## Data boundary

Hermes Windows Guardian is local-only and makes no network requests. It does not read Hermes conversations, memories, configuration files, `.env`, OAuth files, browser profiles, or messaging credentials.

The event log intentionally stores only timestamps, health state, numeric process IDs, recovery action, method, and success state. Command lines and subprocess output are never logged.

## Recovery boundary

The project has no force-kill implementation. It asks the official Hermes Scheduled Task to run, or falls back to the official `hermes gateway start` command. If health evidence is incomplete, it fails safe without recovery.

## Reporting a vulnerability

Do not open a public issue containing credentials, tokens, private paths, conversation text, or full environment dumps. Use GitHub's private vulnerability reporting for this repository. Include a minimal reproduction with secrets removed.

## Scope

This policy covers the code in this repository. Vulnerabilities in Hermes Agent itself should be reported through the upstream project's security process: https://github.com/NousResearch/hermes-agent/security
