# Dogfood Integration — 2026-09-24 — Firewall-as-a-Library (JSON bridge) + uninstall leg

**Angle (9th run):** runs 1–8 covered the CLI, auto-sandbox, rule packs, the plugin in the
live gateway, and seccomp. This run used the surfaces they never touched: the interruptor
as a **Python library consumed from a scratch project** via its documented firewall API
(the `interruptor_bridge.py` JSON protocol, "safe to script" per docs/dogfood/2026-08-10),
and the **documented `--uninstall` path** on a fresh machine.

## Promise under test

"a user can script the firewall: feed one JSON line
`{"command": ...}` to `plugin/terminal_jail/interruptor_bridge.py`, get one JSON verdict
`{action, command, modified, rule_id, reason}` back — and a fresh user can install, verify,
and cleanly uninstall terminal-jail from scratch following the docs."

## What I did

- Wrote a real consumer program (`/tmp/dogfood-tj-20260924/consumer.py`, outside the repo)
  that drives the bridge as a subprocess, asserts the documented verdict contract on the
  happy paths (allow / block / modify / default-allow), and probes the edges a careful
  integrator worries about.
- Fresh-machine leg on an ephemeral bunker-las-03 agent (6776a2da, destroyed after use):
  clone from the public GitHub URL, documented install, documented smoke, then the
  documented `--uninstall` with a user-authored rule staged to test the preserve promise.

## What held up (contract is genuinely good)

- Happy paths: allow names its rule (`allow-ls`), block names its rule
  (`builtin-rm-rf-root`), modify carries the rewritten command + rule (`auto-make`), and
  default-allow is honestly marked with `rule_id: null` — a script CAN tell an approval
  from a pass-through. This was DF-12's complaint in the 09-17 run; as a library
  consumer I confirm it is fixed.
- Transport failures are structured fail-open with a `[bridge-error]` reason and rc=0:
  invalid JSON, empty stdin, non-dict payload, missing/non-string `command`. No
  tracebacks, no garbage on stdout. A integrator can machine-read every failure.
- Engine-evaluation failures fail CLOSED (`[bridge-error]` → block; TJ-GAP-070).
- Fresh install on a bare Debian user: clone 5s, `./install.sh` <1s, smoke PASS
  (v1.2.0, host FULL, jail PID-ns inode differs from host, blocked test rc=126).
- **Uninstall leg (first real use ever): PASS on every documented promise** — wrapper,
  lib tree, `00-builtins.yaml`, and the rc-file PATH block removed; the user-authored
  `99-mine.yaml` was preserved and listed as `left in place (user-authored)`; second
  `--uninstall` run was an idempotent no-op rc=0.

## Finding 1 — long commands hang the engine (P1)

One 8KB argument costs **7.5s of pure CPU** inside the bridge; 20KB+ never returns
(timed out at 10s in a bisect). The blowup is superlinear in argument length:

| arg length | bridge wall time |
|---|---|
| 500 B | 0.11s |
| 2,000 B | 0.65s |
| 8,000 B | 9.22s (7.5s engine + startup; intercept() alone = 7.491s) |
| 20,000 B | >10s (gave up) |

cProfile names the hot path precisely: `matcher.py:115 _match_pattern` — 145
`re.Pattern.search` calls, **7.555s of 7.566s (99.8%) of self-time**. The rule regexes
backtrack catastrophically on long arguments. The parser is innocent (0.004s).

Why it matters beyond speed: the deployed shim evaluates EVERY shell invocation through
this bridge before exec. Any agent command that happens to carry a multi-KB argument
(a base64 blob, a heredoc captured in a variable, a long prompt echo) freezes the shell
for seconds to forever — a latency self-DoS reachable without any security rule firing.
Cheapest mitigations for the maintainer: a length guard (commands over N KB skip
regex matching and emit a conservative verdict), or per-rule timeouts
(`regex` module / RE2-style engines), or pre-compiling rules with possessive
quantifiers/atomic groups where the patterns allow it.

Reproduce:
```bash
python3 - <<'EOF'
import json, subprocess, sys, time
cmd = "echo " + "a" * 8000
t = time.time()
subprocess.run([sys.executable, "plugin/terminal_jail/interruptor_bridge.py"],
               input=json.dumps({"command": cmd}), capture_output=True, text=True, timeout=30)
print(f"{time.time()-t:.2f}s")
EOF
```

## Finding 2 — `--list-rule-packs` exits 2 on a fresh host (P2)

On a bare machine without PyYAML, the purely informational `./install.sh --list-rule-packs`
prints the pack list AND then refuses with `rule-pack-tool: refused: shipped pack ...
cannot be read (PyYAML is not installed...)`, exiting 2. This differs from the plain
install's documented and correct behavior (pack install is a **skip, not a failure**,
rc=0). Consequence: any docs/bootstrap script that chains
`./install.sh --list-rule-packs && ./install.sh` aborts before installing anything —
that is exactly how the first install attempt on the bunker produced zero files while
looking like a run. An informational listing that cannot list what it cannot parse
should print `db: unreadable (PyYAML missing)` and exit 0.

## Finding 3 — docs gap: the JSON bridge is undocumented in quickstart (P2)

The bridge protocol lives only in a 2026-08-10 dogfood report and the module docstring.
Nothing in docs/quickstart.md, README, or docs/ tells a library consumer the one JSON
line in / one JSON line out contract, the field semantics (when is `rule_id` null),
or the fail-open vs fail-closed split (TJ-GAP-070). I had to read
`interruptor_bridge.py` source to confirm the contract before relying on it — the
skill counts "had to read source to proceed" as a finding. Suggested fix: a short
"Scripting the firewall" section in docs/quickstart.md §3b.

## Verdict on the library angle

The firewall API is **trustworthy as a script surface** (structured verdicts, honest
default-allow provenance, fail-closed engine path) but **not yet safe to put in front of
arbitrary command lengths**. P1 fix is small and targeted at matcher.py:115.

## Consumer snippet that worked (the integration pattern)

```python
import json, subprocess, sys


def verdict(cmd: str) -> dict:
    p = subprocess.run(
        [
            sys.executable,
            "/path/to/terminal-jail/plugin/terminal_jail/interruptor_bridge.py",
        ],
        input=json.dumps({"command": cmd}),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(p.stdout.splitlines()[-1])


v = verdict("ls -la")
assert v["action"] == "allow" and v["rule_id"] == "allow-ls"
v = verdict("rm -rf /")
assert v["action"] == "block" and v["rule_id"] == "builtin-rm-rf-root"
v = verdict("make test")
assert v["action"] == "modify" and v["modified"].startswith("unshare --user")
```

## Fix verification — Finding 1 (TJ-DF-024, 2026-09-24)

> **STATUS OF THE SECTION BELOW: attempt 1 is REJECTED and superseded by
> attempt 2.** Read both; attempt 1's text is kept as the audit trail of what
> was tried first and why it did not ship.

### Attempt 1 — REJECTED (length fastpath; foreman verdict: security regression)

**Fix:** an engine-side length guard in `intercept()` (`plugin/terminal_jail/interruptor/__init__.py`),
ahead of parse and every regex layer. A command longer than the matching budget is
ALLOWED without regex evaluation and marked `rule_id="over-length-fastpath"` with a
`[over-length] …` reason naming the command's length, the budget, and the knob. This is
an allow-with-marker, not a block: the deny-list posture is unchanged, and the marker is
deliberately NOT a rule id (a rule would have to be mirrored into `00-builtins.yaml`,
and a matching rule would still pay regex cost on exactly the payloads the fast path
skips) — a script can now distinguish fast-path pass-throughs from both an approved
allow rule and a default-allow (`rule_id: null`).

**Knob:** `TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH` (read by
`interruptor/config.py` like every other interruptor env var — it is real, not a
reserved name). Default `4000`; `0` disables the guard; garbage/negative values fall
back to the default so a typo cannot silently disarm the guard. 4000 sits below the
8KB repro payload, so every payload in the finding's bisect table takes the fast path.

**Measured on this worktree** (same bridge protocol, same machine class as the
finding; wall time includes interpreter startup):

| arg length | before fix | after fix | verdict after |
|---|---|---|---|
| 2,000 B | 0.65s (bridge) | 0.74s (bridge, below budget — unchanged matching path) | `allow` / `allow-echo` |
| 8,000 B | 9.22s (bridge; 7.491s in intercept()) | **0.048s** (bridge) | `allow` / `over-length-fastpath` |
| 20,000 B | no verdict (killed at 12s on this host; >10s in the finding) | **0.066s** (bridge) | `allow` / `over-length-fastpath` |
| 200,000 B | no verdict (killed at 15s on this host) | **0.057s** (bridge) | `allow` / `over-length-fastpath` |

(The before-fix re-measurement on today's tree is marginally worse than the satellite's
9.22s — 10.2s intercept() wall at 8KB — so the table stays honest: both numbers are
catastrophic, the fix is not being graded against the friendlier one.)

Per-rule profile at HEAD confirmed the finding's cProfile attribution — 99%+ of the
cost is `matcher.py _match_pattern`, dominated by four no-match scans on long tokens
(`builtin-interp-egress-http-file` ≈2.5s/call, `builtin-fork-bomb` ≈1–1.5s, the
`builtin-interp-egress-socket-*` pair ≈0.7s each), and the parser is innocent
(70ms at 200KB). The fast path skips that entire evaluation class.

**Tests:** `plugin/test_over_length_fastpath.py` — 19 tests: both acceptance payloads
through the real bridge subprocess (8KB <2s wall with the explicit verdict shape; the
<200ms/<1s acceptance numbers live in this doc, the tests pin only the order of
magnitude so a loaded CI host cannot flake), an over-length `sudo …` prefix allowed
(not re-classified to block), marker-vs-rule-id provenance (the marker is absent from
all three BUILTIN_* layers), disabled/warn-mode interactions, short-command parity
(`allow-echo`/`allow-ls` unchanged, a 4,000-char `echo` still matches `allow-echo`
because the guard is strictly `> budget`), and the knob (default, raise, lower, `0` =
off, garbage fallback, and the env var reaching a real bridge subprocess).

**Residual (unchanged by this fix):** commands between ~2KB and the 4,000-char budget
still pay superlinear regex cost (2KB = 0.74s bridge wall) — the acceptance criterion
only covers the >N KB class, and lowering the budget trades match coverage for latency.
A structural fix for the four hot no-match patterns (atomic groups / possessive
quantifiers) remains open if sub-second behavior below the budget ever matters.

### Attempt 2 — SHIPPED (required-substring prefilters; the attempt-1 fix above is NOT in the tree)

Attempt 1 was reverted (commit "Revert fix: over-length fast path" on
`wt/TJ-DF-024`): a live probe showed a padded 8KB echo carrying a destructive
suffix returned `allow / over-length-fastpath` — a block-rule trigger hidden
behind padding was never evaluated. The foreman rejected it as a security
regression and attempt 2 (worker re-dispatch) produced no code, so the fix was
landed foreman-direct.

**Shipped approach** (`plugin/terminal_jail/interruptor/matcher.py`): a
required-substring prefilter table `_PATTERN_PREFILTERS` keyed by the EXACT
builtin pattern string. For the four catastrophic no-match patterns
(`builtin-fork-bomb`, `builtin-interp-egress-socket-shell/-file`,
`builtin-interp-egress-http-file`), the first-match lookahead of each pattern
is a disjunction of alternatives each containing at least one case-stable
LITERAL ("socket"; "urlopen"/"requests"/"httpx"/"urllib"/".request("; "|" for
the fork-bomb backreference form). When NONE of a pattern's alternative
literals is present (casefolded both sides to honor IGNORECASE), the pattern
cannot match, so skipping the regex evaluation is provably safe. Patterns
without a table entry are ALWAYS evaluated — a same-id user override whose
pattern differs never hits the key and is never skipped; new rules are safe
by default. No length knob exists: there is no length above which evaluation
is skipped, so the deny list holds at ANY command length. The rejected
`TERMINAL_JAIL_INTERRUPTOR_MAX_COMMAND_LENGTH` knob was removed with the
revert (a test pins `Config` has no such field).

**Measured (in-process intercept() wall, warm):**

| arg length | before (base 9d00d52) | after (attempt 2) | verdict after |
|---|---|---|---|
| 2,000 B | 0.65s (bridge) | 0.026s | `allow` / `allow-echo` |
| 8,000 B | 9.22s (bridge); 10.5s intercept() re-measured at base | **0.024s** | `allow` / `allow-echo` |
| 20,000 B | no verdict (killed at 12s) | **0.053s** | `allow` / `allow-echo` |
| 200,000 B | no verdict (killed at 15s) | **0.495s** | `allow` / `allow-echo` |
| 8KB pad + destructive suffix | slow-but-correct block at base | **0.006s** | `block` / `builtin-rm-rf-root` |

Soundness proofs pinned by tests (`plugin/test_tjdf024_prefilter.py`, 18
tests): an 8KB padded destructive command still blocks; an 8KB fork-bomb form
still blocks; an 8KB python socket-reverse-shell one-liner still blocks; an
upper-case trigger in a long command still blocks (casefold path); every
alternative literal ALONE in an 8KB command still blocks (regression pin on
the any/all inversion the escape-wave suite caught during development); a
non-protected block rule (kill -9 -1) is unaffected at 8KB; benign
8KB/20KB/200KB all evaluate to allow with `rule_id != over-length-fastpath`
(evaluated, never skipped); every protected pattern is a table key; the
over-length marker cannot reappear.

Full suite at the fix: 1430 passed / 7 skipped (baseline 1405+7 + 18 new + 7
net test moves from the revert); ruff check + format clean.

**Residual:** commands whose text DOES contain a trigger literal pay the
pattern's regex cost (they match or miss on the full pattern — correct and
typically fast because a match short-circuits; the 8KB padded-destructive
probe returned in 6ms). Non-triggered long commands are now the cheap class
everywhere, which is the payload class the finding measured.
