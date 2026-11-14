# Dogfood run — 2026-11-14: the documented deny-by-default path, and a rule that looks armed but is not

Tick: `terminal-jail-dogfood-2026-11-14-10-01-04` · lane workdir `/home/kara/.hermes/stand-in/dogfood/terminal-jail`

Product checkout: `/home/kara/terminal-jail`, HEAD `489bbd4` = `origin/main` (0 ahead / 0 behind at
start, clean tree). The only working-tree change this run made is the one board row it filed
(`TJ-DF-066`), this report, its diagnostics entries and the dogfood-log line.
Installed CLI under test: `~/.local/bin/terminal-jail` → `terminal-jail 1.3.3`.
Install leg: clean-machine battery on `bunker-mvp`, agent `51fa2112` (see §F).

Verdict: **WORKS AS DOCUMENTED, WITH ONE SILENT HOLE** — the deny-by-default workflow the quickstart
recommends (a catch-all block rule in `~/.config/terminal-jail/rules.d/`) behaves exactly as promised,
a schema-broken rule file fails closed with a readable refusal, unknown `action:` is now warned about,
and containment is real on both the installed CLI and the checkout. But a rule whose `match.type` is
not in the engine's vocabulary **loads silently and never fires**: no warning, `rule_id: null`, and
`rules-drift-probe` still reports it as a healthy extension rule. A user can believe a protective rule
is armed when it is dead.

## Why this angle

The previous entry (2026-11-11) drove the *first run* and the false containment warning. The obvious
next question a new user asks is the one the quickstart answers at `docs/quickstart.md:543`: *"I do not
want a permission list, I want everything denied unless I said otherwise — how?"* That paragraph gives a
recipe (catch-all block rule under `rules.d/`) and no schema. So the run became: follow the recipe
literally, as a user with no knowledge of the engine, and see whether the protection is real and
whether its failure modes are visible.

## What a user is promised

| Source | Claim |
|---|---|
| `docs/quickstart.md:543` | for deny-by-default, add a catch-all block rule under `~/.config/terminal-jail/rules.d/`; it "denies everything the built-in allow rules do not already match" |
| `docs/rule-catalog.md:103` | built-in rules are `match: type: pattern` (regex, `re.search`, `IGNORECASE`) |
| commit `9020095` (QA-TERMINAL-JAIL-30) | an unknown `action:` must not silently disable a rule |
| `plugin/terminal_jail/interruptor/rules.py:183-184` | "unknown `match.type` is a no-op today (MatchResult() with matched=False), so only the TYPES of the keys present are validated here" |
| `docs/quickstart.md` §3a | a canary outside the jail is unreadable inside it |
| carried `TJ-DF-048` | the fs tier costs about +120 ms per invocation |

## What actually happened

### A. The documented deny-by-default recipe — works exactly as written

`/home/kara/.hermes/cache/scratch/tj-dogfood-20261114/usr-catchall/rules.d/99-catchall.yaml`:

```yaml
rules:
  - id: user-deny-by-default
    description: "Catch-all deny for everything the builtin allow rules do not match (quickstart 3b)"
    priority: 1
    action: block
    block_message: "No rule allowed this command (deny-by-default)."
    match:
      type: pattern
      pattern: "."
```

With `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR` pointed at that dir and `MODE=enforce`:

```
$ ./standalone/terminal-jail date
{"event":"verdict","action":"block","rule_id":"user-deny-by-default","layer":"user"}   BLOCKED  rc=126
$ ./standalone/terminal-jail echo hello
{"event":"verdict","action":"allow","rule_id":"allow-echo","layer":"engine"}          hello      rc=0
$ ./standalone/terminal-jail ls /tmp
{"event":"verdict","action":"allow","rule_id":"allow-ls","layer":"engine"}            …          rc=0
```

Builtin allows at priority 500 win over the user catch-all at 1; unmatched commands fall to it. The
promised semantics hold.

### B. A broken rule file fails CLOSED and says why

`priority: critical` (a string instead of an int):

```
terminal-jail: REFUSING rule file …/usr-badschema/rules.d/99-catchall.yaml: rule #1
(user-catchall-broken): field priority must be an integer, got str ('critical') — fix the field type
(the rules in this file are NOT loaded)
… fail-closed: blocking command (enforce mode)                                          rc=126
```

Good failure: names the file, the rule index, the rule id, the field, the reason, and blocks.

### C. Unknown `action:` is surfaced (the 9020095 fix, verified live at HEAD)

`action: teleport` on `^uname`:

```
terminal-jail: WARNING — User rule 'user-teleport-uname' has unknown action 'teleport' — allowing (fail-safe)
```

Exactly the treatment the closed row promised. So the *sibling* gap in §D is not an oversight in
priority — it is a gap the same fix did not cover.

### D. Unknown `match.type:` loads silently and never fires — **finding `TJ-DF-066`**

Two rules, identical but for one line, a priority-900 block on `^date$`:

| `match` | Verdict | Command result |
|---|---|---|
| `type: pattern, pattern: "^date$"` | `block` / `user-block-pattern-type` | BLOCKED, rc 126 |
| `type: regex,   regex: "^date$"`  | `allow` / `rule_id: null` | **ran**, rc 0, no warning on stderr |

`type: regex` is the natural guess, because `regex` *is* a documented field name in the very same
`match` block (`rules.py:187-210` accepts `regex` as a key). The engine's dispatch has no `regex`
handler, so `matcher.py:157-159` returns a no-match and the rule evaporates:

```python
handler = dispatch.get(match_type)
if handler is None:
    return MatchResult()
```

The silence is the harm, and it is total — the only operator surface that inspects user rules
*blesses* the dead rule:

```
$ python3 scripts/rules-drift-probe.py      # same dirs, same instant
RESULT: drift=0 overridden=0 corrupt=0 unoverridden=55 non-builtin=1
INFO: non-builtin rule id(s) present (extension mechanism, never drift): user-block-regex-type
```

`drift=0`, "non-builtin rule id(s) present" — an operator reading that concludes the rule is installed
and healthy. `scripts/rule-pack-tool.py schema` *does* enumerate the vocabulary
(`pattern`/`path`/`composite`/`syscall`/`network`/`heredoc`/`subcommand`), but the quickstart's
user-rule paragraph never points at it, and `TJ-DF-035` added that discoverability for rule *packs*
only. Filed as `TJ-DF-066` with the A/B, the two file:line citations and both remedies
(warn like `action` does; make the drift probe flag a handler-less `match.type`).

### E. Containment is real, on both binaries

Canary `/home/kara/tj-dogfood-canary/secret.txt` (`TIER-CANARY`, dir 755, file 644, readable from the
host by plain `cat`):

| CLI | default (tier on) | `TERMINAL_JAIL_LANDLOCK=0` |
|---|---|---|
| checkout `./standalone/terminal-jail` | `cat: … Permission denied`, rc 1 | prints `TIER-CANARY`, rc 0 |
| installed `~/.local/bin/terminal-jail` | `cat: … Permission denied`, rc 1 | prints `TIER-CANARY`, rc 0 |

Tier off → read succeeds, tier on → read fails, so the kernel tier is genuinely attached on both.

**Deploy note, not a row** (per the skill's deploy-note rule): the *installed* 1.3.3 build (2026-11-10)
still prints the `TJ-DF-064` false warning on every command —

```
terminal-jail: WARNING: Landlock filesystem tier not applied (landlock-loader.py is not reachable by
the launch's payload uid …); commands run unchanged without kernel filesystem enforcement …
```

— while the canary above proves the tier IS enforcing through that same installed path. The fix
(`ae8524e`) is in HEAD and verified; the host install simply predates it. Re-running `install.sh` on
this host closes `TJ-DF-064`'s user-visible half; no code work is implied.

### E2. The binary a user actually gets is not the one I tested — and it is broken

Every arm above invoked an explicit path. A real user types `terminal-jail`. On this host that resolves
elsewhere:

```
$ type -a terminal-jail
terminal-jail is /tmp/tj-test-pack2/terminal-jail      ← first on PATH
terminal-jail is /home/kara/.local/bin/terminal-jail   ← the 1.3.3 install
$ terminal-jail --version
terminal-jail 1.2.0

$ terminal-jail cat /home/kara/tj-dogfood-canary/secret.txt
+--------------------------------------------------------------+
|  COMMAND BLOCKED — interruptor-bridge-unavailable            |
+--------------------------------------------------------------+
rc=126      # and it is unwaivable: TERMINAL_JAIL_LANDLOCK=0 gives the same box

$ terminal-jail --no-interruptor date
Sat Nov 14 05:19:29 AM -05 2026   rc=0      # only escape hatch: disarm the firewall
```

So on this host the default user experience of the documented commands is *every command refused*, with
a workaround (`--no-interruptor`) that turns the product off. Two carried rows already own this and
neither needs re-filing:

- `OPS-TJ-001` (pending, P2) — the root cause: `~/.profile` exports stale `/tmp` PATH entries, so the
  1.2.0 test-pack copy shadows the real install. Owner-gated: the unattended harness cannot write
  `~/.profile` (refused 2026-11-10 and again 2026-11-13, not worked around). This run confirms the
  symptom is still live on 2026-11-14 and that the 1.3.3 install behind it is *not* the broken one.
- `TJ-DF-061` (complete) — the bridge-error defect itself, fixed in the code; the 1.2.0 binary predates
  the fix, so this is a stale artifact, not a regression. Verified by contrast: the checkout CLI and the
  1.3.3 install both run commands fine in the same shell.

This is the single most user-visible defect on the host and it is invisible from the repo: `install.sh`
says installed, `--version` on the resolved binary says 1.2.0.

### F. Performance (Step 2b) — nothing a user would feel, nothing new to file

`hyperfine --warmup 3 -r 20 --style basic`, clean env (see the trap below):

| command | mean ± σ |
|---|---|
| `~/.local/bin/terminal-jail true` (tier on) | **245.1 ± 7.8 ms** |
| `./standalone/terminal-jail true` (tier on) | 242.8 ± 6.0 ms |
| `env TERMINAL_JAIL_LANDLOCK=0 … true` | 178.0 ± 7.6 ms |
| `env TERMINAL_JAIL_SANDBOX=off … true` | 250.2 ± 10.6 ms |

The fs tier costs **+67 ms** (~+38%) per wrapped command; `TERMINAL_JAIL_SANDBOX=off` saves nothing, so
the sandbox launch is not the cost. That is the same order as carried `TJ-DF-048` (which recorded
+120 ms on 10-17); the delta is smaller today, the premise is unchanged, no new row.

**Measurement trap worth recording:** a first pass measured 126 ms and looked like a 2× win. It was
wrong — an exported `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR` from the §A arm was still in the shell,
so every wrapped command was short-circuited by the catch-all *block rule* before any sandbox launched.
Rule-level blocks are cheap; wrapping is not. Any wrap timing taken while a deny rule is active is
measuring the rule, not the product.

### G. Install leg — clean machine, not skipped

`bunker-qa.sh launch /home/kara/terminal-jail` → agent `51fa2112` on `bunker-mvp` (ttl 4h),
`resolve` pre-check printed the product root `/home/kara/terminal-jail`. First collected cells:

```
launch              OK  agent=51fa2112 server=bunker-mvp ttl=4h script_bytes=139101
toolchain-bootstrap OK  go 1.27.4 installed (discovered; ~/tools/go; floor=none ambient=1.22.2 installed=1.27.4)
toolchain-bootstrap OK  python venv ready + pytest (~/tools/venv)
toolchain-bootstrap OK  system gcc/g++ toolchain (~/tools/bin wrappers)
toolchain-bootstrap OK  make available (preinstalled) — GNU Make 4.3
toolchain-bootstrap OK  jq installed (static jq-linux64 -> jq-1.8.2)
fresh-install       OK  Successfully installed PyYAML-6.0.3 terminal-jail-1.3.3; no artifact expected for [pip install -e .[dev] …]
lint                N/A no supported lint trigger (declared linter, Makefile lint target, package lint script, ruff, or Go files)
```

`fresh-install` **OK** on a machine that has never seen the project — the install leg is a real pass,
not a silent one. Remaining cells were still running when this report was written; the evidence file is
`/tmp/bunker-qa-evidence-20261114T101500Z-2836405.jsonl` (agent kept, ttl 4h).

## Verdict

- Does it work? **Yes** — the documented deny-by-default recipe, the fail-closed schema, the JSON
  bridge and containment all reproduce. On *this host*, though, a real user typing `terminal-jail` gets
  a stale 1.2.0 binary that refuses every command (§E2) — carried by `OPS-TJ-001`, not by this run.
- Is it useful? **Yes** — deny-by-default is a working pattern, not a demo; one rule converts the
  allow-list model into a deny-list one.
- Is it usable? **Mostly** — but the user-rule paragraph ships no schema, and the vocabulary has to be
  discovered from `scripts/rule-pack-tool.py schema` or from source.
- Is it trustworthy? **Not yet, on one axis** — a dead rule is indistinguishable from an armed one, and
  the drift probe says it is fine (`TJ-DF-066`).

## Findings filed

| id | priority | subject |
|---|---|---|
| `TJ-DF-066` | P2 | unknown `match.type` loads silently and never fires; no warning, drift probe reports it healthy |

Not filed, deliberately: the fs-tier cost (carried by `TJ-DF-048`, no measurable change a user would
notice), the stale host install (deploy note in §E, no code work implied), and the PATH shadowing /
bridge refusal (§E2 — root cause already owned by the pending, owner-gated `OPS-TJ-001`; the code defect
itself is closed by `TJ-DF-061`, so re-filing would be a duplicate).

## Left behind

- `TJ-DF-066` appended to `.coding-hermes/board/tasks.jsonl` (`boardctl validate` → `RESULT: OK`).
- This report; a diagnostics entry in `docs/dogfood/diagnostics.md`.
- One line in `.coding-hermes/dogfood-log.md`.
- No code change; no repo visibility or permission change; the bunker agent is left for its ttl.
