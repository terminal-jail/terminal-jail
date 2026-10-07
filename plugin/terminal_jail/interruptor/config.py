"""Configuration for the interruptor — loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


class Config:
    """Runtime configuration for the interruptor rule engine.

    Loaded from environment variables. All attributes have default values
    so the interruptor can operate without any configuration.
    """

    __slots__ = (
        "log_level",
        "max_arg_bytes",
        "mode",
        "system_rules_dir",
        "user_rules_dir",
    )

    VALID_MODES = ("enforce", "warn", "disabled")

    # TJ-GAP-086: enforced maximum argument size (UTF-8 bytes). The gate in
    # ``intercept()`` refuses (clean BLOCK naming this knob and the limit)
    # any command whose UTF-8 size exceeds it — BEFORE parsing/evaluation —
    # so a stall-sized argument costs O(len), never the linear scan curve
    # (~0.2 ms/KB measured; scripts/arg_size_benchmark.py re-measures it).
    # 256 KiB sits far above real commands and above TJ-DF-024's 200 KB
    # benign-latency fixtures (those still evaluate). Raise or lower it with
    # TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES; unset/invalid values fall
    # back to this default (fail-safe: a typo must never re-arm unbounded
    # evaluation).
    DEFAULT_MAX_ARG_BYTES = 262144

    def __init__(
        self,
        mode: str = "enforce",
        system_rules_dir: str = "/etc/terminal-jail/rules.d",
        user_rules_dir: str = "",
        log_level: str = "WARNING",
        max_arg_bytes: int | None = None,
    ) -> None:
        if mode not in self.VALID_MODES:
            mode = "enforce"
        self.mode = mode
        self.system_rules_dir = system_rules_dir
        self.user_rules_dir = user_rules_dir or str(
            Path.home() / ".config" / "terminal-jail" / "rules.d"
        )
        self.log_level = log_level.upper() if log_level else "WARNING"
        if max_arg_bytes is None:
            max_arg_bytes = self.coerce_max_arg_bytes(
                os.environ.get("TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES", "")
            )
        self.max_arg_bytes = max_arg_bytes

    @classmethod
    def coerce_max_arg_bytes(cls, raw: str) -> int:
        """Coerce the env knob to a usable limit; anything unusable → default.

        Fail-safe on purpose: an empty, non-integer, zero, negative, or
        float-looking value falls back to DEFAULT_MAX_ARG_BYTES so a typo'd
        knob can never re-arm unbounded evaluation.
        """
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            return cls.DEFAULT_MAX_ARG_BYTES
        if value <= 0:
            return cls.DEFAULT_MAX_ARG_BYTES
        return value

    @classmethod
    def from_environ(cls) -> Config:
        """Load configuration from environment variables."""
        return cls(
            mode=os.environ.get("TERMINAL_JAIL_INTERRUPTOR_MODE", "enforce"),
            system_rules_dir=os.environ.get(
                "TERMINAL_JAIL_INTERRUPTOR_RULES_DIR",
                "/etc/terminal-jail/rules.d",
            ),
            user_rules_dir=os.environ.get(
                "TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR", ""
            ),
            log_level=os.environ.get("TERMINAL_JAIL_INTERRUPTOR_LOG_LEVEL", "WARNING"),
            max_arg_bytes=cls.coerce_max_arg_bytes(
                os.environ.get("TERMINAL_JAIL_INTERRUPTOR_MAX_ARG_BYTES", "")
            ),
        )

    def __repr__(self) -> str:
        return (
            f"Config(mode={self.mode!r}, "
            f"system_rules_dir={self.system_rules_dir!r}, "
            f"user_rules_dir={self.user_rules_dir!r}, "
            f"log_level={self.log_level!r}, "
            f"max_arg_bytes={self.max_arg_bytes!r})"
        )
