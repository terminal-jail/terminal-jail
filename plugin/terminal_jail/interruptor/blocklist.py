"""Built-in critical blocklist rules for the interruptor.

These rules are ALWAYS active and cannot be removed — only overridden to
``warn`` level by user rules. They ship with the interruptor package.
"""

from __future__ import annotations

from .rules import Rule

BUILTIN_BLOCKLIST: list[Rule] = [
    Rule(
        rule_id="builtin-kill-all",
        description="Mass process kill",
        priority=1000,
        action="block",
        block_message="Mass process kill (kill -9 -1) is blocked.",
        match={
            "type": "pattern",
            # Mass-kill invariant: in `kill` syntax, signal specs come
            # first, then pid operands. `-1` is a MASS-KILL PID when it
            # is NOT the first operand (kill 123 -1, kill -9 -1,
            # kill -1 -1) or when preceded by `--` (kill -- -1);
            # `-1` in first-operand position is a SIGNAL (kill -1 123
            # is SIGUSR1 to pid 123 — legit). TJ-GAP-053: quote chars
            # added to the terminator class so quoted/embedded forms
            # (node -e 'execSync("kill -9 -1")', kill -9 "-1") match too.
            # = SIGHUP, benign). The pattern requires at least one
            # operand before the pid `-1` (signal spec and/or pid),
            # excludes `-1` as the argument of -s/-n/-l (not a pid),
            # and ends at a token/segment boundary so compound forms
            # (kill -- -1; echo x, kill -9 -1 && echo hi) still match.
            # `(?<!\S)` is the token-start boundary (plain \b can never
            # sit between a space and a dash); re.IGNORECASE covers
            # -TERM/-SIGKILL.
            "pattern": r"(?<![A-Za-z0-9])kill\s+(?:-s\s+\S+\s+|-n\s+\S+\s+|--\s+|-(?!l)\S+\s+|\d+\s+)+(?<!-s\s)(?<!-n\s)(?<!\S)-1(?:\s|;|\||&|\)|`|$|[\"'])",
        },
    ),
    Rule(
        rule_id="builtin-killpg-pid1",
        description="Process-group kill targeting PID 1 or own process group (killpg API)",
        priority=1000,
        action="block",
        block_message="Process-group kill targeting PID 1 or own process group (killpg(0/1, ...)) is blocked — this is the MagicMock incident vector.",
        match={
            "type": "pattern",
            "pattern": r"(os\.killpg|killpg)\s*\(\s*[01]\s*,|os\.kill\s*\(\s*[01]\s*,|process\.kill\s*\(\s*-?[01]\s*,|kill\(-?[01],|kill\s*\(\s*[01]\s*,\s*(9|SIGKILL)",
        },
    ),
    Rule(
        rule_id="builtin-fork-bomb",
        description="Fork bomb pattern (any function name, not just ':')",
        priority=1000,
        action="block",
        block_message="Fork bomb pattern detected and blocked.",
        match={
            "type": "pattern",
            # Tolerate arbitrary whitespace between `:|:&` so the
            # wrapper-quoted argv form ``':' '(){' ':' '|:' '&' '};:'``
            # (which produces ``: (){ : |: & };:`` after the bridge
            # strips the per-token quote pairs) is still caught.
            # TJ-GAP-053: named-func variants (bomb(){ bomb|bomb & };bomb)
            # passed the classic pattern — generalized via backreference.
            # Guards are LOOKAROUNDS, not \b: ':' is non-word so \b never
            # matches before it (regression: classic form must stay caught);
            # lookarounds exclude word-char neighbors on both sides, which
            # still defeats substring tricks (bomb(){ bombard|bomb & };bomb).
            "pattern": r"([A-Za-z_]\w*|:)\s*\(\s*\)\s*\{[^}]*(?<![\w:])\1\s*\|\s*\1(?![\w:])[^}]*&[^}]*\}\s*;\s*\1(?![\w:])",
        },
    ),
    Rule(
        rule_id="builtin-rm-rf-root",
        description="Recursive root filesystem removal",
        priority=1000,
        action="block",
        block_message="Recursive root directory removal (rm -rf /) is blocked.",
        match={
            "type": "pattern",
            # Root-scoped recursive-delete rule (TJ-DF-001): the flag set
            # is matched order-independently via two lookaheads (any
            # recursive flag: -r/-R/--recursive, possibly combined like
            # -rf/-fr; any force flag: -f/--force), and the target must be
            # exactly "/" or "/*" (root glob). This catches the canonical
            # GNU forms `rm -rf --no-preserve-root /`, `rm -r -f /`,
            # `rm --recursive --force /`, and `rm -rf/`. `(?<!\S)` is the
            # token-start boundary (plain \b can never sit between a space
            # and a dash); re.IGNORECASE covers -R. TJ-GAP-042: the target
            # boundary is extended to quotes/parens/backtick so destructive
            # commands EMBEDDED in quoted interpreter args (python3 -c
            # "...", bash -c '...', echo "rm -rf /") also trip the rule —
            # previously only whitespace/end-of-string qualified, so the
            # quoted forms passed as ALLOW (battery-proven 2026-08-22).
            "pattern": r"\brm\s+(?=[^|;&]*(?<!\S)(?:-[a-z]*r[a-z]*|--recursive)\b)(?=[^|;&]*(?<!\S)(?:-[a-z]*f[a-z]*|--force)\b)[^|;&]*\s*/(?:\*)?(?:\s|$|[\"')`])",
        },
    ),
    Rule(
        rule_id="builtin-dd-root",
        description="Raw device write via dd",
        priority=1000,
        action="block",
        block_message="Raw device writes (dd to /dev/*) are blocked.",
        match={
            "type": "pattern",
            "pattern": r"dd\s+.*of=/dev/",
        },
    ),
    Rule(
        rule_id="builtin-mkfs",
        description="Filesystem creation",
        priority=1000,
        action="block",
        block_message="Filesystem creation commands (mkfs.*) are blocked.",
        match={
            "type": "pattern",
            # Match ``mkfs.<type>`` (e.g. mkfs.ext4) AND the bash-syntax
            # variant ``mkfs .ext4`` where the type is a separate argv
            # token (the wrapper-quoted form ``'mkfs' '.ext4' ...``
            # surfaces as ``mkfs .ext4 /dev/sdb1`` once the bridge strips
            # the per-token quote pairs). The lookahead avoids matching
            # benign text that merely mentions ``mkfs`` (e.g.
            # ``echo mkfs``).
            "pattern": r"mkfs(?:\.|\s+\.)",
        },
    ),
    Rule(
        rule_id="builtin-fdisk",
        description="Partition manipulation",
        priority=1000,
        action="block",
        block_message="Partition manipulation (fdisk, parted, gdisk) is blocked.",
        match={
            "type": "pattern",
            "pattern": r"fdisk|parted|gdisk",
        },
    ),
    Rule(
        rule_id="builtin-chmod-777-root",
        description="World-writable root",
        priority=1000,
        action="block",
        block_message="Setting world-writable permissions on root (/) is blocked.",
        match={
            "type": "pattern",
            # World-writable mode on a /-rooted path (TJ-DF-011): the mode
            # token (777, 7777, or a+rwx) is matched order-independently via
            # a lookahead, and the recursive flag (-R/--recursive) via an
            # OPTIONAL second lookahead — plain `chmod 777 /` must still
            # block. The target keeps the old `\s+/` semantics: ANY path
            # starting with / (e.g. /var/www) blocks, which is intentional
            # and tested. `(?<!\S)` is the token-start boundary (plain \b
            # can never sit between a space and a dash); re.IGNORECASE
            # covers -R.
            "pattern": r"\bchmod\s+(?=[^|;&]*(?<!\S)(?:7777|777|a\+rwx)\b)(?=[^|;&]*(?<!\S)(?:-[a-z]*r[a-z]*|--recursive)\b)?[^|;&]*\s+/",
        },
    ),
    Rule(
        rule_id="builtin-echo-to-system",
        description="Redirect output to system paths",
        priority=1000,
        action="block",
        block_message="Writing to system paths (/etc/, /boot/) is blocked.",
        match={
            "type": "pattern",
            "pattern": r">\s*/etc/|>>\s*/etc/|>\s*/boot/|>>\s*/boot/",
        },
    ),
    Rule(
        rule_id="builtin-curl-pipe-shell",
        description="Curl/wget piping to shell",
        priority=1000,
        action="block",
        block_message="Piping downloads directly to a shell is blocked. Use package managers instead.",
        match={
            "type": "pattern",
            "pattern": r"(curl|wget)\b.*\|\s*(bash|sh|dash|zsh)",
        },
    ),
    Rule(
        rule_id="builtin-sudo",
        description="Privilege escalation via sudo/doas/su/pkexec",
        priority=1000,
        action="block",
        block_message="Privilege escalation (sudo/doas/su/pkexec) is blocked in the sandbox.",
        match={
            "type": "pattern",
            # TJ-GAP-053: sudo was the only covered escalator; doas/su/pkexec
            # passed (probe 2026-09-16). \bsu\s requires whitespace so sudo/
            # support/setuptools substrings never match.
            "pattern": r"\b(?:sudo|doas|pkexec|su)\s",
        },
    ),
    Rule(
        rule_id="builtin-code-injection",
        description="Code-injection vectors in interpreter arguments (os.system, os.popen, shutil.rmtree, subprocess, eval, exec, __import__)",
        priority=1000,
        action="block",
        block_message="Code-injection vectors (os.system/os.popen/shutil.rmtree/subprocess/eval/exec/__import__) are blocked — quoted interpreter code is scanned, not just shell syntax.",
        match={
            "type": "pattern",
            # TJ-GAP-042: the rm-rf-root rule previously only matched a
            # root target followed by whitespace/end-of-string, so
            # destructive code inside QUOTED interpreter arguments
            # (python3 -c '...os.system("rm -rf /")...',
            # python3 -c "...eval(open('/etc/passwd').read())...")
            # passed as ALLOW. This rule scans the RAW command string for
            # the Python/Ruby exec API surface — same design as
            # builtin-killpg-pid1 (block on presence anywhere). Spec T-I33
            # ("heuristic detection") was parser-only; this makes it a
            # real block rule. Battery-proven gap 2026-08-22 (kara-lair).
            "pattern": r"\b(os\.system|os\.popen|shutil\.rmtree|subprocess\.(?:call|run|Popen|check_call|check_output))\s*\(|\b(eval|exec|__import__)\s*\(",
        },
    ),
    # ── TJ-GAP-053 wave (probe 2026-09-16: 25 real-world escape techniques) ──
    Rule(
        rule_id="builtin-indirect-shell",
        description="Encoded/piped shell execution (base64 -d | sh, printf-decode | bash)",
        priority=1000,
        action="block",
        block_message="Decode-then-execute pipelines (base64/printf | sh) are blocked — the firewall cannot inspect what runs.",
        match={
            "type": "pattern",
            "pattern": r"\bbase64\s+[^|;]*\|\s*(bash|sh|dash|zsh|ksh)\b|\b(printf|echo)\b[^|;]*\\x[0-9a-f]{2}[^|;]*\|\s*(bash|sh|dash|zsh|ksh)\b",
        },
    ),
    Rule(
        rule_id="builtin-vm-delete",
        description="Bulk unlink via find -delete",
        priority=1000,
        action="block",
        block_message="find -delete / -exec bulk or arbitrary-command execution is blocked.",
        match={
            "type": "pattern",
            # Any find (absolute or relative) arming -delete/-exec/-ok:
            # -delete is rm-class destruction, -exec/-ok is arbitrary
            # command execution per matched file. Plain finds stay allowed.
            "pattern": r"\bfind\s[^|;&]*\s-(?:delete|exec|execdir|ok)\b",
        },
    ),
    Rule(
        rule_id="builtin-device-write",
        description="Raw device writes outside dd (shred, wipefs, cat/urandom redirects)",
        priority=1000,
        action="block",
        block_message="Raw block-device writes (shred/wipefs/cat > /dev/sd*) are blocked.",
        match={
            "type": "pattern",
            "pattern": r"\b(?:shred|wipefs|blkdiscard)\b[^|;&]*\s/dev/|>\s*/dev/(?:sd[a-z]|nvme\d|hd[a-z]|vd[a-z]|mmcblk\d)",
        },
    ),
    Rule(
        rule_id="builtin-ns-escape",
        description="Namespace/jail escape tooling (nsenter into a foreign PID, chroot, setpriv to uid 0)",
        priority=1000,
        action="block",
        block_message="Namespace escape tooling (nsenter -t <pid>, chroot, setpriv/setuid to 0) is blocked.",
        match={
            "type": "pattern",
            "pattern": r"\bnsenter\s[^|;&]*-t\s|\bchroot\s|\bsetpriv\s[^|;&]*--(?:reuid|setuid|clear-groups)\b|\bunshare\s[^|;&]*-r\b",
        },
    ),
    Rule(
        rule_id="builtin-persistence",
        description="Persistence install (crontab write, rc.local, systemd unit drop)",
        priority=1000,
        action="block",
        block_message="Persistence writes (crontab -, /etc/cron*, rc.local, systemd units) are blocked.",
        match={
            "type": "pattern",
            "pattern": r"\bcrontab\s+(?:-(?:\s|$)|-l?\s*<|-[a-z]*\s*/etc/)|/etc/cron\.(?:d|daily|hourly)/|/etc/rc\.local\b|/etc/systemd/system/[^|;&]*\.(?:service|timer)\b",
        },
    ),
    Rule(
        rule_id="builtin-script-killall",
        description="killall/pkill with SIGKILL (mass-kill by process name)",
        priority=1000,
        action="block",
        block_message="killall/pkill -9 is blocked (mass kill by name). Non-KILL killall/pkill is allowed for legit restarts.",
        match={
            "type": "pattern",
            "pattern": r"\b(?:killall|pkill)\s+(?:-[a-zA-Z]*9[a-zA-Z]*\s|--signal\s*(?:SIGKILL|9)\s|--kill\s)",
        },
    ),
    Rule(
        rule_id="builtin-interpreter-escape",
        description="Interpreter APIs that destroy state (perl/ruby/node/python: unlink, rm_rf, rmSync, fork loops, execSync of kills)",
        priority=1000,
        action="block",
        block_message="Interpreter destruction APIs (unlink/rm_rf/rmSync/execSync-masskill/os-fork-loop) are blocked — same design as the code-injection rule.",
        match={
            "type": "pattern",
            # Covered forms: perl unlink/rmtree, ruby FileUtils.rm_rf,
            # node fs.rmSync + child_process.execSync("kill -9 -1"),
            # python os.fork() loops (fork-bomb via API).
            # child_process.exec/execSync arming requires a kill shape in
            # the SAME command string (probe 2026-09-16: node-exec-kill).
            "pattern": r"\bperl\b[^|;&]*\bunlink\b|\bperl\b[^|;&]*\brmtree\b|FileUtils\.rm_rf\(|\brmSync\s*\(|child_process\.(?:exec|execSync)\s*\([^)]*(?:kill|rm)\b|os\.fork\s*\(\s*\)\s*(?:while|for)|while\s+[^;\n]*:\s*os\.fork\s*\(",
        },
    ),
    Rule(
        rule_id="builtin-self-rewrite",
        description="Self-modification vectors (rm on the rules/config itself, mv-over",
        priority=1000,
        action="block",
        block_message="Rewriting terminal-jail's own rules/config is blocked.",
        match={
            "type": "pattern",
            "pattern": r"\brm\s+[^|;&]*terminal-jail/(?:rules|00-builtins)|\bmv\s+[^|;&]*\s[^|;&]*terminal-jail/rules|\bcat\s+[^|;&]*>\s*/etc/terminal-jail/|>\s*~/.config/terminal-jail/rules",
        },
    ),
    Rule(
        rule_id="builtin-var-indirection",
        description="Variable-indirection shell destruction (D=/; rm -rf $D and friends)",
        priority=1000,
        action="block",
        block_message="Variable-indirection destructive forms (var=/ then rm -rf $var) are blocked.",
        match={
            "type": "pattern",
            # Root assigned to a var, then an rm of that var — the var must
            # be a bare `/` or `/*` assignment to qualify as root-scoped.
            "pattern": r"\b[A-Za-z_]\w*=/\s*;\s*rm\s+(?=[^|;&]*-[a-zA-Z]*r)|\b[A-Za-z_]\w*=/\*\s*;\s*rm\s+(?=[^|;&]*-[a-zA-Z]*r)",
        },
    ),
]
