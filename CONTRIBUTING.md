# Contributing

Thanks for helping Windows users keep their Hermes messaging Gateway reliable.

## Before opening a change

1. Search existing issues and pull requests.
2. Keep the project local-only and dependency-light.
3. Never include real credentials, chat content, `.env` files, private logs, or user-specific paths.
4. Preserve the fail-safe rule: unknown health must not trigger recovery.
5. Do not add a force-kill path without an explicit design discussion.

## Development

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m hermes_windows_guardian.cli --json check
```

Pull requests should include a regression test and a concise explanation of the Windows behavior being fixed.
