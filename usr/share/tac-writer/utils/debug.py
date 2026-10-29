"""Debug logging gated by TAC_DEBUG environment variable."""

from __future__ import annotations

import os


def tac_debug_enabled() -> bool:
    return bool(os.environ.get("TAC_DEBUG"))


def debug_print(*args, **kwargs) -> None:
    if tac_debug_enabled():
        kwargs.setdefault("flush", True)
        print(*args, **kwargs)
