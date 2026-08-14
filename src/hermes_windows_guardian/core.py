from __future__ import annotations

import re
from collections.abc import Sequence
from enum import Enum
from pathlib import Path


class Health(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"


def looks_like_gateway(argv: Sequence[str] | str) -> bool:
    """Match only the Hermes gateway runtime, never status/diagnostic commands."""
    if isinstance(argv, str):
        normalized = argv.lower().replace("\\", "/")
        has_module = bool(
            re.search(r"(?:^|\s)-m\s+hermes_cli\.main(?:\s|$)", normalized)
        )
        has_runtime = bool(re.search(r"(?:^|\s)gateway\s+run(?:\s|$)", normalized))
        return has_module and has_runtime
    args = [str(item).lower().replace("\\", "/") for item in argv]
    try:
        module_at = args.index("-m")
    except ValueError:
        return False
    if module_at + 1 >= len(args) or args[module_at + 1] != "hermes_cli.main":
        return False
    return any(args[i : i + 2] == ["gateway", "run"] for i in range(len(args) - 1))


def classify_health(cli_status: str, gateway_pids: list[int] | None) -> Health:
    """Fail safe: only declare death when both independent signals are negative."""
    if gateway_pids:
        return Health.ALIVE
    if cli_status == "alive":
        return Health.ALIVE
    if cli_status == "dead" and gateway_pids == []:
        return Health.DEAD
    return Health.UNKNOWN


def redact_text(text: str, private_roots: Sequence[str | Path]) -> str:
    redacted = text
    for root in sorted(
        (str(item) for item in private_roots if str(item)), key=len, reverse=True
    ):
        redacted = re.sub(
            re.escape(root), "<redacted-home>", redacted, flags=re.IGNORECASE
        )
    redacted = re.sub(
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        r"\1=<redacted>",
        redacted,
    )
    return redacted
