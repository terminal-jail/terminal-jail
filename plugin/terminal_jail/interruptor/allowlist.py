"""Built-in allowlist rules for the interruptor.

These commands are always allowed (never blocked, never sandboxed).
"""

from __future__ import annotations

from .rules import Rule

BUILTIN_ALLOWLIST: list[Rule] = [
    Rule(
        rule_id="allow-echo",
        description="Safe text output",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^echo\s"},
    ),
    Rule(
        rule_id="allow-ls",
        description="Directory listing",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^ls\b"},
    ),
    Rule(
        rule_id="allow-pwd",
        description="Print working directory",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^pwd$"},
    ),
    Rule(
        rule_id="allow-cat-safe",
        description="Safe file reads (non-sensitive paths)",
        priority=500,
        action="allow",
        match={
            "type": "pattern",
            "pattern": r"^cat\s(?!.*/(etc|boot|proc|sys))",
        },
    ),
    Rule(
        rule_id="allow-grep",
        description="Text search",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^grep\s"},
    ),
    Rule(
        rule_id="allow-find-safe",
        description="File search without -exec/-delete",
        priority=500,
        action="allow",
        match={
            "type": "pattern",
            "pattern": r"^find\s(?!.*-exec)(?!.*-delete)",
        },
    ),
    Rule(
        rule_id="allow-git-read",
        description="Git read operations",
        priority=500,
        action="allow",
        match={
            "type": "pattern",
            "pattern": r"^git\s+(status|log|diff)\b",
        },
    ),
    Rule(
        rule_id="allow-python-version",
        description="Python version check",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^python.*--version"},
    ),
    Rule(
        rule_id="allow-which",
        description="Path resolution",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^(which|command\s+-v)\s"},
    ),
    Rule(
        rule_id="allow-cd",
        description="Directory change",
        priority=500,
        action="allow",
        match={"type": "pattern", "pattern": r"^cd\s"},
    ),
]
