"""TJ-GAP-053 escape-wave regression tests.

Vectors gathered from real-world attacker technique classes (2026-09-16
probe session): indirection/obfuscation, interpreter escapes, mass-kill
variants, generalized fork bombs, bulk deletion, raw device writes,
non-sudo privilege escalation, namespace/jail escape tooling, and
persistence installs. Each vector here was an ACTUAL allow-verdict gap
at some point before its fix — keep them all green forever.

By-design allow verdicts (killall without SIGKILL, crontab -l reads,
relative-path finds) are pinned in TestEscapeWaveAllows so no future
"hardening" accidentally over-blocks legit operations.
"""
import pytest

from terminal_jail.interruptor import Action, intercept

# (technique name, command, expected rule_id)
BLOCK_VECTORS = [
    # indirection / obfuscation
    ("var-indirection", "D=/; rm -rf $D", "builtin-var-indirection"),
    ("quoted-binary", "'rm' -rf /", "builtin-rm-rf-root"),
    ("xargs-indirection", "echo / | xargs rm -rf /", "builtin-rm-rf-root"),
    ("bash-c-indirection", "bash -c 'D=/; rm -rf $D'", "builtin-var-indirection"),
    ("base64-pipe-sh", "echo cm0gLXJmIC8= | base64 -d | sh", "builtin-indirect-shell"),
    # interpreter escapes
    ("perl-system-rmrf", "perl -e 'system(\"rm -rf /\")'", "builtin-rm-rf-root"),
    ("perl-unlink-glob", "perl -e 'unlink glob \"/etc/*\"'", "builtin-interpreter-escape"),
    ("ruby-rmrf", "ruby -e 'FileUtils.rm_rf(\"/\")'", "builtin-interpreter-escape"),
    ("node-rmsync", "node -e 'require(\"fs\").rmSync(\"/etc\",{recursive:true})'", "builtin-interpreter-escape"),
    ("node-exec-kill", "node -e 'child_process.execSync(\"kill -9 -1\")'", "builtin-kill-all"),
    ("python-fork-loop", "python3 -c 'import os\nwhile True: os.fork()'", "builtin-interpreter-escape"),
    ("python-getattr", "python3 -c 'import os; getattr(os, \"system\")(\"rm -rf /\")'", "builtin-rm-rf-root"),
    # mass-kill variants
    ("killall-sigkill", "killall -9 sshd", "builtin-script-killall"),
    ("pkill-dot", "pkill -9 -f .", "builtin-script-killall"),
    ("quoted-kill", "kill -9 \"-1\"", "builtin-kill-all"),
    # fork bombs (classic + named)
    ("classic-forkbomb", ":(){ :|:& };:", "builtin-fork-bomb"),
    ("quoted-argv-forkbomb", "':' '(){' ':' '|:' '&' '};:'", "builtin-fork-bomb"),
    ("named-forkbomb", "bomb(){ bomb|bomb & };bomb", "builtin-fork-bomb"),
    ("func-forkbomb", "f(){ f|f & };f", "builtin-fork-bomb"),
    # bulk deletion
    ("find-delete-root", "find / -delete", "builtin-vm-delete"),
    ("find-delete-etc", "find /etc -name '*.conf' -delete", "builtin-vm-delete"),
    ("find-exec-shell", "find /tmp -name '*.sh' -exec bash {} \\;", "builtin-vm-delete"),
    # raw device writes
    ("urandom-to-device", "cat /dev/urandom > /dev/sda", "builtin-device-write"),
    ("shred-device", "shred -n 1 /dev/sda", "builtin-device-write"),
    ("wipefs", "wipefs -a /dev/sda", "builtin-device-write"),
    # privilege escalation beyond sudo
    ("doas", "doas cat /etc/shadow", "builtin-sudo"),
    ("su-root", "su root -c 'cat /etc/shadow'", "builtin-sudo"),
    ("pkexec", "pkexec bash", "builtin-sudo"),
    ("setpriv-reuid", "setpriv --reuid 0 bash", "builtin-ns-escape"),
    # jail/namespace escape tooling
    ("nsenter-init", "nsenter -t 1 -m bash", "builtin-ns-escape"),
    ("chroot", "chroot / /bin/bash", "builtin-ns-escape"),
    # persistence
    ("crontab-stdin", "echo '* * * * * x' | crontab -", "builtin-persistence"),
    ("crontab-trailing-dash", "crontab -", "builtin-persistence"),
    ("systemd-unit-drop", "echo x > /etc/systemd/system/evil.service", "builtin-echo-to-system"),  # echo-to-system (> /etc/) fires first; both block
]

ALLOW_VECTORS = [
    ("killall-restart", "killall sshd"),          # non-KILL restart stays legal
    ("pkill-restart", "pkill -HUP nginx"),
    ("crontab-read", "crontab -l"),
    ("find-relative", "find . -name '*.py'"),
    ("find-flags-no-delete", "find /var/log -name '*.log' -mtime +7"),
    ("python-print", "python3 -c 'print(1)'"),
    ("support-word", "cat support-notes.txt"),  # \bsu\s must not match substrings
    ("sudo-none-word", "grep sudoers notes.txt"),
]


class TestEscapeWaveBlocks:
    """TJ-GAP-053: every vector was a real allow-gap before its rule landed."""

    @pytest.mark.parametrize(
        "name,command,rule_id",
        BLOCK_VECTORS,
        ids=[v[0] for v in BLOCK_VECTORS],
    )
    def test_escape_vector_blocked(self, name: str, command: str, rule_id: str) -> None:
        result = intercept(command)
        assert result.action == Action.BLOCK, (
            f"escape vector {name!r} is no longer blocked: {command!r} -> "
            f"{result.action} (rule={result.rule_id!r})"
        )
        assert result.rule_id == rule_id, (
            f"escape vector {name!r} claimed by wrong rule: expected "
            f"{rule_id!r}, got {result.rule_id!r}"
        )


class TestEscapeWaveAllows:
    """By-design allows: hardening must never over-block these."""

    @pytest.mark.parametrize(
        "name,command",
        ALLOW_VECTORS,
        ids=[v[0] for v in ALLOW_VECTORS],
    )
    def test_legit_operation_allowed(self, name: str, command: str) -> None:
        result = intercept(command)
        assert result.action == Action.ALLOW, (
            f"legit operation {name!r} over-blocked: {command!r} -> "
            f"{result.action} (rule={result.rule_id!r})"
        )
