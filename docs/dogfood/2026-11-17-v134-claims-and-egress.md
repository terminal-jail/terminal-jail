# Dogfood 2026-11-17 — v1.3.4's three headline claims, driven as a stranger

Tick: `terminal-jail-dogfood-2026-11-17-11-52-37`
Target: `/home/kara/terminal-jail` at HEAD `9aff5bd` (= `origin/main`, `git rev-list --left-right --count HEAD...origin/main` = `0 0`)
Install channel used: the documented source channel (`./install.sh` from a checkout), into throwaway HOMEs.
Verdict: **WORKS AS DOCUMENTED** — every v1.3.4 release-note claim I drove held, the policy-authoring
workflow is real end to end, and the flagship egress tier is kernel-real. One recurrence filed
(stale version literals) and one new fresh-machine test-hygiene defect filed.

## Promise (null hypothesis)

> A user can install terminal-jail from a checkout without root, have every shell command judged
> against a deny-by-default rule set before it runs, wrap the launch in real kernel containment
> (PID namespace, Landlock filesystem + optional Landlock TCP-egress tiers), and extend their own
> policy through rule packs — with every degradation stated rather than silent.

v1.3.4 (`docs/releases/v1.3.4-notes.md`) adds three claims on top of that:
1. unsupported user-rule `match.type` is **surfaced** (rule id + accepted types) instead of silently not matching;
2. Landlock degradation warnings describe the **actual** cause;
3. the **bundled CLI is synchronized** with the standalone CLI.

## Time to first success (clean HOMEs, this host, load ~17 on 16 cores)

| milestone | wall clock | evidence |
|---|---|---|
| `./install.sh --no-path` (source channel, fresh HOME) | **0.68 s** rc=0 | `install.out`/`install.err` |
| first wrapped command (`terminal-jail --version`) | +0.02 s | same shell |
| first *enforced* verdict (custom block rule, rc=126) | +3 s of authoring | arm 2 |
| external rule pack authored → installed → ENFORCING | ~10 s of authoring | arm 3 |
| blocker | none — no undocumented flag was needed to complete any arm | — |

Friction count: 2 (both minor, both recorded below). Nothing required reading source to *use*;
source was read only to attribute causes, which is the expected use of a maintainer surface.

## Arm 1 — the three v1.3.4 claims (source install, fresh HOME)

Install output: `terminal-jail 1.3.4`; installer reports
`fs tier CAN engage and net (egress) tier CAN engage on this host (Landlock ABI 8 >= 4; opt in with TERMINAL_JAIL_LANDLOCK_NET=1)`
plus a truthful `DEGRADED: mapped launch failed (... AppArmor profile 'unprivileged_userns')` line.

**Claim 1 (unknown `match.type` surfaced) — HOLDS, twice over.**

A user rule `type: regex` (the natural guess, `regex` being a legal *field* name in the same block)
at `priority: 900, action: block` on a non-allow-listed command:

```
terminal-jail: WARNING - user rule 'user-block-probe' has unknown match.type 'regex' — it will never
fire (the engine cannot evaluate that type); accepted types: command, composite, heredoc, network,
path, pattern, pipeline, subcommand, syscall (file: .../rules.d/zz-badtype.yaml)
{"event":"verdict","action":"allow","rule_id":"user-block-probe","layer":"user",
 "reason":"User rule 'user-block-probe' has Unknown match type 'regex'; accepted types: ..."}
```

The command then runs (rc=0) — fail-safe, not fail-closed, and the reason is in the audit trail.
Control arm, same rule with `type: pattern`: `rc=126`, banner `COMMAND BLOCKED — user-block-probe`,
`"layer":"user"`. So the difference between an armed and a dead rule is now visible in both the
stderr warning and the verdict record. **TJ-DF-066's silent hole is closed.**

**Claim 2 (degradation warnings describe the actual cause) — HOLDS.** On a launch whose loader was
unreachable the message named the exact cause and the path, not an unrelated toggle:
`landlock-net-loader.py is not reachable by the launch's payload uid (a parent of ... lacks o+x — e.g.
a 0700/0750 home)`. On the host that *does* apply the tier, a proven apply announces itself:
`landlock-net: kernel egress tier APPLIED — TCP connect() restricted to ports [22, 53, 80, 443]`.

**Claim 3 (bundled CLI synchronized) — HOLDS byte-for-byte.**

```
5ff90915e38a0a878a4ec0f63c53c205  standalone/terminal-jail
5ff90915e38a0a878a4ec0f63c53c205  plugin/terminal_jail/_bundled/terminal-jail   (91,493 B each)
798902ebb40b190dbdcb181e4df5764c  standalone/seccomp-loader.py
798902ebb40b190dbdcb181e4df5764c  plugin/terminal_jail/_bundled/seccomp-loader.py
```

## Arm 2 — the egress tier is KERNEL-REAL (not a rule, not a promise)

Probe: a Python consumer that attempts two TCP connects — port **4444** (outside the default
allowlist) and **443** (inside it). Baseline without the jail, then three arms through the wrapper.
Rig note: the first attempt ran from a HOME under a `0700` parent; the payload died at exec
(`Permission denied`) and only the *loaders* were unreachable — that is the known pending
`TJ-REVIEW-074-R2` defect, not a tier result. Re-run from a world-traversable `/tmp` HOME:

| arm | env | port 4444 | port 443 | verdict |
|---|---|---|---|---|
| baseline, no jail | — | TIMEOUT (upstream) | CONNECTED | reference |
| tier OFF (shipped default) | — | TIMEOUT | CONNECTED | identical to baseline |
| tier ON | `TERMINAL_JAIL_LANDLOCK_NET=1` | **errno=13 Permission denied** | CONNECTED | kernel denies, allowlist honoured |
| tier ON, deny-all | `…_NET=1 …_NET_ALLOW=` (empty) | errno=13 | **errno=13** | deliberate deny-all works |

`errno=13` is `EACCES` from the kernel, and the wrapper prints the `kernel egress tier APPLIED`
notice on the same run, so a kernel denial is distinguishable from an interruptor verdict — exactly
what the README claims. This is the strongest evidence of the run: containment is real, and the
opt-in default (tier ships off) is honest about itself.

## Arm 3 — the policy-authoring workflow a team actually uses

`--list-rule-packs` → `db (14 rules)`, `example-pack (1 rule)`. Then an **externally authored**
pack, the documented path for "my team's policy":

```yaml
rules:
  - id: pack-my-team-pack-guard
    priority: 950
    action: block
    match: {type: pattern, pattern: '^whoami$'}
```

`./install.sh --no-path --rule-pack-file ~/policy/my-team-pack.yaml` → rc=0, byte-copied to
`~/.config/terminal-jail/rules.d/terminal-jail-pack-my-team-pack.yaml` (197 B).
Enforcement: `terminal-jail whoami` → **rc=126**, `"rule_id":"pack-my-team-pack-guard","layer":"pack"`.
`--uninstall-rule-pack-file` → rc=0, file gone, same command rc=0. Refusal arm (id outside the
namespace): **rc=2**, `rules_dir_files_before=2 after=2` (nothing written), one stderr reason
naming the derived namespace, base install completed, `SUMMARY — at least one requested rule pack
was skipped`. The validator refuses an unknown `match.type` inside a pack too
(`match type 'regex' is not dispatchable by the engine (valid: [...])`, exit 2) — so a pack cannot
smuggle in the dead-rule class that arm 1 proves is now warned about at run time.

## Arm 4 — script-facing fidelity (do wrapped commands behave like commands?)

A user wraps `curl`, `make`, `pytest` in scripts; every property below is load-bearing.

```
true            rc=0      false           rc=1      sh -c 'exit 42'  rc=42
ls <missing>    rc=2      printf abc | jail wc -c   -> 3        (stdin passes through)
stdout/stderr split: OUT-LINE to stdout, ERR-LINE to stderr only (0 cross-contamination)
SIGINT to the wrapper's process group (Ctrl-C)  -> rc=130, 0 surviving payload processes
SIGTERM to the wrapper PID (a supervisor)       -> rc=143, 0 surviving payload processes
-- echo hello   rc=127   (the known TJ-DF-067 end-of-options gap, unchanged)
```

Three rig iterations were needed to measure this honestly (`setsid` forks, so `$!` is a dead
parent; bash sets `SIG_IGN` for SIGINT in async jobs without job control). The final design uses
`set -m` + a unique payload marker; the first two produced "survivors" that were artifacts of a
missed kill, which would have been filed as a false orphan-process defect. Recorded in
`diagnostics.md §25.1`.

## Arm 5 — fresh machine (ephemeral bunker install leg)

`bunker-qa.sh resolve` → `/home/kara/terminal-jail`; `launch` → agent **db56b071** @ bunker-mvp
(ttl 4h). Terminal ledger harvested by hand from the agent (24 rows, 8,764 B,
sha256 `99fb55a7f58c35612ca34a8ebbacf24e4ccb405e1bdb2ce7ca665174b0697b8d`,
`CELLS-DONE`): **10 OK, 5 N/A, 3 SKIPPED, 4 FAIL, 1 UNVERIFIED**.

- launch OK; toolchain-bootstrap ×7 OK;
- **fresh-install OK — `Successfully installed PyYAML-6.0.3 terminal-jail-1.3.4`**
  (installability of 1.3.4 on a machine that has never seen the project: PROVEN);
- lint N/A (no lint trigger declared); docker_build / compose_config / ui-probe / chaos-corruption N/A;
  docker-deploy and chaos-shutdown SKIPPED by the controller's own safety gate (live Hermes host);
- **tests FAIL**, and it cascades: the same single test is named by `ci-pass` (native leg),
  `chaos-resource` and `chaos-disconnect` (UNVERIFIED, its cut/log never got a clean suite to grade).
  `chaos-errorpath` OK (rc=2 on a missing config).
- `upgrade` FAIL is the already-pending PyPI channel mismatch (`pip install terminal-jail==1.3.3` →
  "Could not find a version"), owned by `QA-TERMINAL-JAIL-11` — cited, not re-filed.
- `ci-pass` also failed its `Lint (ruff)` and `Drift guards` jobs at **`Main Set up Python`**, with
  `ModuleNotFoundError: No module named '_opcode_metadata'` from the shared
  `/opt/hostedtoolcache/Python/3.13.18` — a hosted-toolcache failure, not a product one; that is the
  class of the pending `QA-TERMINAL-JAIL-14-R2` (act leg racing the shared toolcache), cited not filed.

The `collect` verb twice answered `AGENT-GONE … rows=15` while the agent was **running** and its
battery **finished** (`bunker info` → Status running; `qa-run.log` → `CELLS-DONE`); the full 24-row
ledger was pulled over `bunker exec … cat` before teardown. That collector mis-grade is the known
pending `QA-TERMINAL-JAIL-FOREMAN-1` class — recorded, not re-filed.

The tests FAIL is **attributed**, not a truncation artifact. Pulled from the agent's own per-cell
log (`qa-logs-4189068/tests.log`) before teardown:

```
plugin/test_install.py:271: (test_bin / "unzip").unlink()
E  FileNotFoundError: [Errno 2] No such file or directory: '.../testbin/unzip'
1 failed, 498 passed, 32 skipped in 48.80s
```

`_setup_full_testbin()` symlinks only the tools `shutil.which()` finds on the host
(`_link_tools` silently skips an absent tool), and the test then unlinks `unzip` unconditionally.
The dev host has `/usr/bin/unzip`; a clean image does not. Red-proved locally on the same premise
by running that single test with `PATH` pointing at a bin dir without `unzip`:

```
ARM GREEN (host PATH): 1 passed in 0.15s
ARM RED   (no unzip) : FileNotFoundError: .../testbin/unzip   → 1 failed
```

Filed as **TJ-DF-071** (P2). With `pytest -x` (the harness default) this one test stops the suite
at 3 %, so a clean machine can never show a green suite until the premise is made explicit.

## Step 2b — performance

`hyperfine --warmup 3 -r 20`, warm, this host, **load average 16.5–18.6 on 16 cores** (sibling
lanes compiling), so every wall-clock figure here is a *host* number:

| arm | p50 | mean ± σ | min | max |
|---|---|---|---|---|
| wrapper, tier default | 441.9 ms | 454.7 ± 116.9 ms | 265.3 | 726.3 |
| wrapper, egress tier ON | 383.9 ms | 386.3 ± 48.5 ms | 321.5 | 554.6 |
| 5 sequential first-runs after install | 250–290 ms | — | — | — |

The σ (117 ms) is a third of the mean: the distribution is contaminated by host load, and the
sequential first-run series reproduces the ~245–256 ms figure every earlier fire measured for a
wrapped command. Nothing here is a user-visible regression, and a wrapped command at ~0.25–0.45 s
for a human-launched shell command is below the threshold where anyone notices. **No PERF row is
filed** — the tier-attach cost (~+67 ms) already has `TJ-DF-048`/`PERF-003` owning it, and filing a
load-contaminated number would devalue those rows. True page-cache-cold timing still needs root and
stays unverified.

## Findings

| id | priority | finding |
|---|---|---|
| **TJ-REVIEW-072-R2** | P3 | The `1.3.0` version-literal class recurred after being closed: `plugin/__init__.py:103` and `plugin/terminal_jail/__init__.py:82` still log `terminal-jail v1.3.0 loaded.`, `scripts/metrics-export.py:36` still emits `"version": "1.3.0"` in exported JSON, and `plugin/test_metrics_export.py:97` asserts `== "1.3.0"` — so the test pins the drift. Recurrence of TJ-REVIEW-072, which was closed as "all four named machine surfaces now read 1.3.0"; v1.3.4 is now two releases past that literal. |
| **TJ-DF-071** | P2 | Fresh-machine suite red: `plugin/test_install.py:271` assumes the host has `unzip`; `_link_tools` silently skips absent tools, so on a clean image the shim does not exist and `unlink()` raises `FileNotFoundError` before any assertion. Proved on agent db56b071 (1 failed / 498 passed / 32 skipped in 48.80 s) and red-proved locally with an unzip-free PATH. |

Cited, **not** re-filed (already owned by pending rows):
`RELEASE-TJ-026` (install.sh still defaults `TERMINAL_JAIL_VERSION=1.3.3`, so release-mode install
serves one release behind; `docs/quickstart.md:77` documents that default honestly),
`TJ-REVIEW-074-R2` (the modify path still dies `rc=126` when `python3` resolves inside a `0700`
directory — reproduced this run on the 1.3.4 install),
`TJ-DF-067` (`-- echo hello` → rc=127; unchanged).

## What a new user would still hit

1. **Two warnings for one dead rule.** The unknown-`match.type` case prints a load-time `WARNING`
   line *and* a verdict-reason `WARNING` line with the same text. Correct, but noisy; a
   `--quiet`/dedupe pass would read better. Not filed (polish, no trust cost).
2. **`--uninstall-rule-pack-file` re-installs.** It is an `install.sh` invocation, so it prints the
   full install transcript and (without `--no-path`) rewrites the shell rc PATH block. Documented
   behaviour, surprising the first time. Not filed.
3. **The installer's ceiling line and the runtime line can disagree.** `fs tier CAN engage` at
   install time, then `filesystem tier not applied (no caller-writable ungranted path for the
   enforcement probe)` at run time on a `/tmp` HOME. Both are honest capability-vs-applied
   statements, and the runtime line is the v1.3.4 fix working; recorded for operators
   (`diagnostics.md §25.3`), not filed.

## Files left behind

- this report,
- `docs/dogfood/diagnostics.md` §25 (the run's diagnostic trail, including the three signal-arm rig fixes),
- `skills/terminal-jail-usage/SKILL.md` — "Run 25 additions" (v1.3.4 claims, the egress A/B recipe, the unzip premise),
- `.coding-hermes/evidence/2026-11-17-v134/` — the probe scripts and their raw outputs,
- `.coding-hermes/dogfood-log.md` — the run entry,
- board rows `TJ-REVIEW-072-R2` and `TJ-DF-071`.

## Addendum (same tick, after the push) — main moved under this run

Two facts changed or became explicit between the measurement SHA and the published tip, and both
are stated here rather than left inside an earlier sentence:

1. **Main moved.** Everything above was measured at **`9aff5bd`**. While this fire was writing, a
   sibling lane landed `f7fb7b2` *fix(installer): default release pin serves v1.3.4 assets — Addresses
   RELEASE-TJ-026* and the merge `e91348b`, and my `git push origin HEAD:main` published all three
   commits (`9aff5bd..e91348b`). **`f7fb7b2` and `e91348b` are not this lane's work** — the author
   identity is the fleet's, the change set is `install.sh`, `plugin/test_install.py`,
   `plugin/fixtures/github-release-v1.3.4.json`, `README.md`, `docs/quickstart.md`,
   `docs/releasing.md`, `CONTRIBUTING.md`.
2. **The `RELEASE-TJ-026` citation above is scoped to `9aff5bd`.** At the published tip
   `install.sh:16` now reads `TERMINAL_JAIL_VERSION="${TERMINAL_JAIL_VERSION:-1.3.4}"`, so the
   documented release-mode install serves v1.3.4 assets; the board row is nevertheless still
   `pending` at `e91348b` (fix landed, row unclosed — a foreman closeout, not a dogfood write).

**Both findings survive the move**, re-checked against the committed tree at `e91348b`:

- `TJ-REVIEW-072-R2`: `grep -c 'terminal-jail v1.3.0 loaded'` = 1 in each of `plugin/__init__.py`
  and `plugin/terminal_jail/__init__.py`; `'"1.3.0"'` = 1 in `scripts/metrics-export.py`; `== "1.3.0"`
  = 1 in `plugin/test_metrics_export.py`.
- `TJ-DF-071`: `_link_tools` is unchanged (`if real: symlink_to(real)`) and the unlink is now at
  `plugin/test_install.py:295` (line numbers shifted by the sibling's edits; the mechanism and the
  `FileNotFoundError` are identical). A worker should fix it at HEAD, not at the line number quoted
  from `9aff5bd`.

## Addendum 2 (same tick) — the append-only correction to the previous commit message

The commit `b385093` *"dogfood: disclose the sibling commits this tick's push carried…"* ended with
a sentence claiming that `.gitreins/tasks.yaml` and
`.coding-hermes/waves/terminal-jail-foreman-2026-11-17-11-52-37.json` were "left untouched and
unstaged". **That sentence is false for that commit**: `b385093` actually carried both files (88 and
64 added lines). A sibling **foreman wave** was writing this checkout at the same time — the wave
manifest names the same tick clock (`base_sha 9aff5bd`, `wave_budget 9`, `width 4`) and
`.gitreins/tasks.yaml` gained its `RELEASE-TJ-026` task row — and its staged index was swept up by my
commit, exactly the shared-checkout hazard this repo's earlier records warn about.

What those two files contain, checked at `b385093`: the foreman wave manifest for
`terminal-jail-foreman-2026-11-17-11-52-37` (planning metadata: base ref/sha, budget, width) and one
GitReins task definition for `RELEASE-TJ-026`. Neither is product source, neither is this lane's
work, and neither changes any claim in this report. `d81e573` — the actual dogfood commit — was
clean: `git show --name-only d81e573` contains only this run's board rows, evidence, docs, skill and
log.

Corrected statement: this lane's **own** writes are the ones listed above; `f7fb7b2`, `e91348b` and
the two harness files inside `b385093` belong to sibling lanes and are named, not claimed.
