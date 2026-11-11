# Dogfood run — 2026-11-11: the quickstart first run, and a containment warning that lies

Tick: `terminal-jail-dogfood-2026-11-11-05-38-47` · lane workdir `/home/kara/.hermes/stand-in/dogfood/terminal-jail`
Product checkout: `/home/kara/terminal-jail`, HEAD `bef9e68` = `origin/main` (0 ahead / 0 behind at
start; the only working-tree change this run made is the board rows it filed, plus this report).
Installed CLI under test: `~/.local/bin/terminal-jail` → `terminal-jail 1.3.3` (no `/usr/local/bin`
copy exists).
Verdict: **TRUSTWORTHY, WITH ONE LOUD LIE** — every documented behaviour in `docs/quickstart.md` §3a
and the JSON bridge §3a2 reproduced exactly, on the installed CLI and on the checkout; containment is
real (a canary unreadable inside the jail, readable outside it). But the installed CLI prints a
**false** "Landlock filesystem tier not applied" warning on this machine on every wrapped command,
and the remedy it recommends would turn off the protection that is actually working.

## Why this angle

The last two entries drove the published artifacts (2026-11-08) and the external rule-pack plane
(2026-10-29). What had never been driven end to end is the thing a brand-new user meets first: the
**documented first run in `docs/quickstart.md` §3a**, followed by the **JSON bridge transcript §3a2**,
on the *installed* CLI — and then the question every warning raises: *is this warning true?* That
question became the run, because this host trips the filesystem-tier warning on every command.

## What a user is promised

| Source | Claim |
|---|---|
| `docs/quickstart.md:101` | `terminal-jail --version` prints `terminal-jail 1.3.0` |
| `docs/quickstart.md` §3a | `python3 scripts/pidns-capability-probe.py` → a capability class; host pid-ns vs jailed pid-ns differ |
| `docs/quickstart.md` §3a | `python3 scripts/rules-drift-probe.py` exits 0 always; `--fail-on-drift` exits 1 on drift |
| `docs/quickstart.md` §3a2 | the bridge answers `echo hello` → allow/`allow-echo`, `date` → allow/`null`, `rm -rf /` → block/`builtin-rm-rf-root`, `make test` → modify/`auto-make`; a plain allow always carries **six** fields |
| `standalone/terminal-jail` warning text | the filesystem tier is *not applied* when the loader "is not reachable by the launch's payload uid … commands run unchanged without kernel filesystem enforcement" |
| `docs/quickstart.md:735` | the repo version is 1.3.0 |

## What actually happened

### A. First run, verbatim from §3a

```
$ terminal-jail --version
terminal-jail 1.3.3                                        rc=0            (doc expects 1.3.0)
$ python3 scripts/pidns-capability-probe.py
FULL (backend: bwrap)                                      rc=0   283 ms
$ python3 scripts/rules-drift-probe.py
system dir : /etc/terminal-jail/rules.d (0 rule file(s))
user dir   : /home/kara/.config/terminal-jail/rules.d (2 rule file(s))
engine     : 55 rules (36 block / 9 sandbox / 10 allow)
RESULT: drift=0 overridden=55 corrupt=0 unoverridden=0 non-builtin=1
INFO: non-builtin rule id(s) present (extension mechanism, never drift): dogfood-block-force-push
                                                           rc=0    93 ms
$ python3 scripts/rules-drift-probe.py --fail-on-drift
                                                           rc=0    89 ms
$ readlink /proc/self/ns/pid          → pid:[4026531836]   (host)
$ terminal-jail readlink /proc/self/ns/pid
                                                           → pid:[4026533283]   rc=0   275 ms
$ terminal-jail echo 'in jail'        → in jail           rc=0   263 ms
```

Isolation is real: the wrapped command sits in a different PID namespace from the host, and bwrap is
the backend, not the unshare fallback. The rule engine is at 55 builtin rules with zero drift against
the shipped mirror; the only non-builtin id is a user extension, which the probe classifies as an
extension and not drift — correct.

### B. A refusal, on a safe substitute

The documented "does it actually block" gesture is `rm -rf /`. This run used a non-destructive
equivalent that hits a block rule by scope:

```
$ terminal-jail chmod 777 <scratch>/canary      → COMMAND BLOCKED — builtin-chmod-777-root
                                                  rc=126   140 ms    file mode unchanged: 600
```

The block panel is legible and names the rule; the exit code 126 matches `docs/threat-model.md`.

### C. The documented bridge transcript, §3a2

```
echo hello   → {"action":"allow", "rule_id":"allow-echo",           "layer":"engine", "modified":null, "reason":""}
date         → {"action":"allow", "rule_id":null,                   "layer":"engine", ...}
rm -rf /     → {"action":"block", "rule_id":"builtin-rm-rf-root",   "reason":"Recursive root directory removal (rm -rf /) is blocked."}
make test    → {"action":"modify","rule_id":"auto-make",            "modified":"unshare --user --pid --fork --kill-child=SIGKILL bash -c 'python3 …/landlock-loader.py -- make test'"}
field census on a plain allow: keys = [action, command, layer, modified, reason, rule_id]  n_fields = 6
```

Four for four, and the six-field promise holds. This is the strongest part of the product: the
verdict line protocol is exactly what the docs say, it is stable enough to script, and the
modify verdict shows the sandbox it will attach instead of hand-waving.

### D. The warning that lies (this run's decisive experiment)

On this host every wrapped command prints to stderr:

```
terminal-jail: WARNING: Landlock filesystem tier not applied (landlock-loader.py is not reachable
by the launch's payload uid (a parent of /home/kara/.local/lib/terminal-jail/landlock-loader.py
lacks o+x — e.g. a 0700/0750 home)); commands run unchanged without kernel filesystem
enforcement — classify the host with scripts/landlock-capability-probe.py, or disable this
warning deliberately with TERMINAL_JAIL_LANDLOCK=0
```

Host modes: `/home/kara` **751**, `/home/kara/.local` **700**, installed loader
`~/.local/lib/terminal-jail/landlock-loader.py` **775**. So the named parent (`~/.local`, 700) does
lack `o+x` — the *description* is accurate. The claim built on it is not.

A canary any uid can read was placed at `/home/kara/tj-dogfood-canary/secret.txt` (dir 755, file 644,
`/home/kara` 751): `cat` outside the jail reads `TIER-CANARY` (DAC control). Then four cells:

| cell | CLI | tier | canary inside |
|---|---|---|---|
| A | installed | `TERMINAL_JAIL_LANDLOCK=0` (disabled) | **readable**, rc=0 |
| B | installed | default (warning printed) | **Permission denied**, rc=1 |
| C | checkout | disabled | **readable**, rc=0 |
| D | checkout | default | **Permission denied**, rc=1 |

Disabling the tier flips denial to success on the *installed* CLI. Therefore the filesystem tier **is
applied** on the installed path, and the warning's operative claim ("commands run unchanged without
kernel filesystem enforcement") is **false** on this host. The install-location theory is dead: the
same four-cell result holds for the checkout, whose loader sits in a 755 tree, and the checkout prints
no warning at all — the difference is the warning's reachability test, not delivery of the tier.

Why the test misfires, as a hypothesis for the fixer (not a verified mechanism): the CLI executes the
loader **as the launching user** before any uid/payload mapping, so a 700 parent is traversable for
the loader launch while remaining untraversable for the mapped payload uid — the warning asks "could
the payload reach the loader?" when the only question that matters is "did the loader load?".

Two costs for a real user: (1) a permanent, scary stderr line on every command erodes trust in the
*warnings* generally, including the ones that are true; (2) the remedy it recommends —
`TERMINAL_JAIL_LANDLOCK=0` — silently disables working containment. A user who follows the advice
trades a working tier for silence.

Filed as **TJ-DF-064** (P1).

### E. Version drift in the doc

`docs/quickstart.md:101` pins the expected output to `terminal-jail 1.3.0` and line 735 calls 1.3.0
the repo version; the repo, the installed CLI, and the wheel the bunker built are all **1.3.3**. A new
user's very first command "fails" its documented expectation. Filed as **TJ-DF-065** (P3).

### F. Install leg on a fresh machine (`bunker-qa.sh`)

```
bunker-qa.sh status   → server bunker-mvp · bunkerd=active docker=yes act=no uidmap=yes
bunker-qa.sh launch   → agent d6035ac5
bunker-qa.sh collect  → 15 evidence rows synced
```

Cells: `fresh-install` **OK** — `Successfully installed PyYAML-6.0.3 terminal-jail-1.3.3`, artifact
`/home/bunker-d6035ac5/tools/venv/bin/terminal-jail`; `launch` OK; `toolchain-bootstrap` OK ×10;
`lint`/`docker_build`/`compose_config` N/A (no such surfaces); `tests` **FAIL**, and the failure is
`plugin/test_install.py::test_successful_install`, which **passes in the local checkout**
(`1 passed in 0.54s`). The captured detail stops before the assertion, but the test's shape and the
fresh box's minimal toolchain point at the already-filed **QA-TERMINAL-JAIL-32** (install.sh's wheel
path requires `unzip`, which the fresh image lacks). No new row: filing it would duplicate a pending
P3 for the same test, so the recurrence is recorded here and in the log instead.

Installability verdict: a fresh box installs the package and gets a working `terminal-jail` binary.
So the install channel works; the project's own install *test* does not survive that environment.

### G. What it costs in time (Step 2b)

Measured inside the arms while using the product (no separate timing harness):

```
terminal-jail true     251 260 269 250 253 ms   (n=5, median 253)
bare true                3   4   3   3   4 ms   (n=5, median 3)
bridge evaluate         22  22  23 ms            (python start per call)
pidns capability probe  283 ms   rules-drift 93 ms / 89 ms   blocked chmod 140 ms
```

~250 ms per wrapped command over a ~3 ms bare exec is the price of the jail, and it is the already-known
number: **TJ-DF-048** carries the warm/cold tier cost and the stale README table. Nothing here is a new
perf finding — 250 ms is perceptible on a single command and invisible in a build, and no regression
appeared against the prior figure. **No `PERF-<n>` row filed**, deliberately: filing this again would
devalue the real one. No profile was taken because no number here justifies one.

## Verdict

**TRUSTWORTHY, WITH ONE LOUD LIE.** The documented contract — capability class, drift probe, namespace
isolation, block verdicts, the six-field bridge protocol — reproduced exactly, first try, on both the
installed and checkout CLIs, and the containment it claims is demonstrably enforced. The one failure is
the worst-shaped kind: a *false negative warning* on the installed path, repeated on every command,
whose own remedy (`TERMINAL_JAIL_LANDLOCK=0`) would remove the protection that is working. Fix that and
the first-run experience is honest.

## Rows filed

| id | pri | what |
|---|---|---|
| `TJ-DF-064` | P1 | installed CLI prints a FALSE "filesystem tier not applied" warning while the tier IS enforcing; remedy text disables working protection |
| `TJ-DF-065` | P3 | quickstart pins `--version` to 1.3.0 (line 101) and the repo version to 1.3.0 (line 735) while everything ships 1.3.3 |

Recurrence noted, not re-filed: `QA-TERMINAL-JAIL-32` (pending) — `test_successful_install` fails on a
fresh bunker box, passes locally.

## Evidence

Scratch arms and raw output: `/home/kara/.hermes/cache/scratch/tj-dogfood-20261111/`
(`arm-quickstart-3a.sh`, `arm-bridge-doc.sh`, `arm-landlock-location.sh`, `arm-loader-location.sh`,
`arm-fstier-decisive.sh`, `arm-fstier-dacfree.sh`, `arm-decisive-warn.sh`; `arm-3a.out`,
`arm-bridge.out`, `arm-location2.out`, `arm-fstier.out`, `arm-fstier-dacfree.out`, `arm-decisive.out`;
bunker evidence `/tmp/bunker-qa-evidence-20261111T054830Z-1037424.jsonl`).
Out-of-repo residue: `/home/kara/tj-dogfood-canary/` (755 dir, 644 canary — remove it when the row is
closed; it is the fixture for the decisive test).
