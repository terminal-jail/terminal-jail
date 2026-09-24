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
        "mode",
        "system_rules_dir",
        "user_rules_dir",
    )

    VALID_MODES = ("enforce", "warn", "disabled")

    def __init__(
        self,
        mode: str = "enforce",
        system_rules_dir: str = "/etc/terminal-jail/rules.d",
        user_rules_dir: str = "",
        log_level: str = "WARNING",
    ) -> None:
        if mode not in self.VALID_MODES:
            mode = "enforce"
        self.mode = mode
        self.system_rules_dir = system_rules_dir
        self.user_rules_dir = user_rules_dir or str(
            Path.home() / ".config" / "terminal-jail" / "rules.d"
        )
        self.log_level = log_level.upper() if log_level else "WARNING"

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
        )

    def __repr__(self) -> str:
        return (
            f"Config(mode={self.mode!r}, "
            f"system_rules_dir={self.system_rules_dir!r}, "
            f"user_rules_dir={self.user_rules_dir!r}, "
            f"log_level={self.log_level!r})"
        )
