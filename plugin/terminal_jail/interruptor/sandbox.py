"""Built-in auto-sandbox rules for the interruptor.

These commands are automatically wrapped in an unshare namespace for
additional isolation. They are never blocked, only sandboxed.
"""

from __future__ import annotations

from .rules import Rule

BUILTIN_SANDBOX: list[Rule] = [
    Rule(
        rule_id="auto-pytest",
        description="Python test runner",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: pytest running in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"pytest|tox|nose",
        },
    ),
    Rule(
        rule_id="auto-npm-test",
        description="JavaScript test runner",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: JS test runner in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"npm\s+test|npx\s+(vitest|jest)",
        },
    ),
    Rule(
        rule_id="auto-go-test",
        description="Go test runner",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: Go test runner in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"go\s+test",
        },
    ),
    Rule(
        rule_id="auto-make",
        description="Build system",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: build tool in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"make\s|make$",
        },
    ),
    Rule(
        rule_id="auto-pip",
        description="Package installer",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: package installer in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"pip\s+install|pip3\s+install",
        },
    ),
    Rule(
        rule_id="auto-cargo",
        description="Rust build tool",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: Rust build in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"cargo\s+(build|test)",
        },
    ),
    Rule(
        rule_id="auto-gcc",
        description="C/C++ compilation",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: compilation in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"gcc\s|g\+\+\s|clang\+\+\s",
        },
    ),
    Rule(
        rule_id="auto-script",
        description="Script execution",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: script execution in isolated namespace.",
        match={
            "type": "pattern",
            "pattern": r"\./(.+\.(sh|py|rb|zsh|bash|ksh)|[^/]+\.(sh|py|rb|zsh|bash|ksh))|\b(bash|sh|dash|zsh|python3?|ksh)\s+[^\s|;&]+\.(sh|py|rb|zsh|bash|ksh)",
        },
    ),
    # ── TJ-GAP-058 network-egress wave (dual-use egress shapes get ──────────
    # ── sandboxed rather than blocked: the fleet runs these for real work) ──
    Rule(
        rule_id="builtin-net-fetch-pipe-qualified",
        description="Fetch pipeline into a path-qualified or wrapped interpreter",
        priority=700,
        action="sandbox",
        block_message="Auto-sandboxed: downloaded script piped into a path-qualified/wrapped shell (namespace isolation, command still runs).",
        match={
            "type": "pattern",
            # Companion to builtin-curl-pipe-shell, which BLOCKS the bare
            # interpreter form (`curl <url> | sh`) in its whole-command pass.
            # That pattern cannot see a PATH-QUALIFIED or WRAPPED interpreter,
            # so `curl <url> | /bin/sh` and `curl <url> | env sh` were plain
            # ALLOW; they are dual-use (a real installer vs a staged
            # download-execute) and get the namespace wrap instead of a block.
            #
            # Structure matters here: the DECIDER runs block rules against the
            # WHOLE command string but evaluates the sandbox layer PER
            # SEGMENT, and the parser splits `curl <url> | /bin/sh` into two
            # segments (`curl <url>`, `/bin/sh`). A pipe-spanning sandbox
            # pattern is therefore unreachable, so arms 1-2 match the STAGE
            # the pipe produces: a path-qualified / wrapped interpreter
            # carrying only flags and fd redirects — i.e. an interpreter
            # reading its program from stdin, with no script operand
            # (`/bin/bash -x deploy.sh` and `bash --version` do NOT match).
            # Arm 3 keeps the explicit whole-pipeline spelling, which stays
            # one segment when it is embedded in a quoted interpreter arg
            # (`sh -c 'curl <url> | /bin/sh'`).
            "pattern": r"^\s*(?:(?:env|busybox|setsid|xargs)\s+(?:-{1,2}[A-Za-z0-9-]+\s+)*)?(?:/usr)?/bin/(?:bash|sh|dash|zsh|ksh)\b(?:\s+(?:-{1,2}[A-Za-z0-9-]+|\d?>&?\d+))*\s*$|^\s*(?:env|busybox|setsid|xargs)\s+(?:-{1,2}[A-Za-z0-9-]+\s+)*(?:bash|sh|dash|zsh|ksh)\b(?:\s+(?:-{1,2}[A-Za-z0-9-]+|\d?>&?\d+))*\s*$|(?<![\w.-])(?:curl|wget)\b[^|;&]*\|\s*(?:(?:env|busybox|setsid|xargs)\s+)?(?:/usr)?/bin/(?:bash|sh|dash|zsh|ksh)\b|(?<![\w.-])(?:curl|wget)\b[^|;&]*\|\s*(?:env|busybox|setsid|xargs)\s+(?:bash|sh|dash|zsh|ksh)\b",
        },
    ),
    # ── DF-TERMINAL-JAIL-20: the local-file egress rules (curl uploads,
    # ── wget file-body POST, curl multipart file field, whole-tree
    # ── rsync/scp copy) moved to blocklist.py as BLOCK rules. They used to
    # ── be auto-sandbox rules here, but the namespace wrap does not restrict
    # ── network access: `curl -T <secret> <collector>` was rewritten INTO
    # ── the sandbox and the payload still reached a live collector. A rule
    # ── whose stated job is to stop an upload has to block it.
]
