# Changelog

## 0.1.1 - 2026-08-13

- Honor Hermes' persisted operator intent before recovery.
- Block recovery after intentional stop or when state is missing or unreadable.
- Preserve custom home and state-directory arguments in the Scheduled Task.
- Document existing upstream supervision and Guardian's known limits.

## 0.1.0 - 2026-08-13

- Add conservative two-signal Gateway health classification.
- Add strict Windows Gateway process detection.
- Add windowless current-user Scheduled Task installation.
- Add cooldown, maintenance disable flag, and privacy-minimal JSONL events.
- Add Scheduled Task recovery with official Hermes CLI fallback.
