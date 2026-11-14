# Fire 3 verification deltas — terminal-jail dogfood tick 2026-11-14-10-01-04

Continuation fire. No code was modified by this lane, no board state was touched, no
install leg was re-run. This document carries the checks the two earlier fires of this
tick **deferred** or left as **open boundaries** — and, because `main` moved under this
fire, a live re-verification of what landed.

- Tick: `terminal-jail-dogfood-2026-11-14-10-01-04`
- Prior records: `2026-11-14a` (run, commit `beb1e59`), `2026-11-14b` (install ledger + teardown, commit `cbbfe42`)
- HEAD when this fire started: `cbbfe42`
- **HEAD when this fire finished: `8c8097e`** (= `origin/main`, `git rev-list --left-right --count HEAD...origin/main` → `0 0`)
- Product pin the earlier numbers came from: `489bbd4`

## 0. Disclosure: main moved during this fire (shared checkout)

`/home/kara/terminal-jail` is a shared checkout and a sibling foreman lane was writing it
while this fire ran. Between 10:45Z and 10:49Z it landed four commits on top of `cbbfe42`:

```
8c8097e chore: correct TJ-DF-064 trace commit binding
a7fa4bb chore: bind TJ-DF-064 trace marker to implementation
88cf92f fix: suppress false mapped Landlock degradation warning
a48809c fix: suppress false mapped Landlock degradation warning
```

Touching `plugin/terminal_jail/_bundled/terminal-jail`, `standalone/terminal-jail`,
`plugin/test_tjdf047_fs_degrade_plain_allow.py`. It also left harness-owned paths dirty in
the worktree (`.gitreins/tasks.yaml`, `.gitreins/usage.jsonl` — a completed `TJ-DF-064-R2`
judge task, graded 10:51:31Z). Those are **not this lane's writes**; they were left
byte-untouched and excluded from this fire's commit, which stages only the two record paths
named at the bottom. No index lock existed and no gitreins process had this checkout as its
cwd at commit time.

Consequence: a check that was true an hour ago is no longer true. Section 3 says which one,
and sections 5 and 8 re-do the work instead of inheriting it.

## 1. Deferred item: CI at the record's own HEAD

Neither earlier fire quoted a hosted CI verdict. Closed here, per sha:

| sha | role | CI |
|---|---|---|
| `489bbd4` | product pin (fire-1 numbers came from here) | **success** 04:22:00Z |
| `3c31d3a` | sibling commit before this tick's closeouts | **success** 10:18:41Z |
| `b73c57a` | fire-1 closeout | **success** 10:29:13Z |
| `cbbfe42` | fire-2 closeout | **success** 10:45:37Z |
| `8c8097e` | **current HEAD**, incl. the TJ-DF-064 fix | **success** 10:48:49Z |

Command: `gh run list --limit 6 --json headSha,status,conclusion,workflowName,createdAt`.
One workflow (`CI`) per sha — no second-workflow contradiction to report. The two
intermediate fix commits (`a48809c`, `88cf92f`) were superseded within minutes and carry no
run of their own; `8c8097e` is the tip that was graded.

## 2. Deferred item: teardown census (independent of fire 2's claim)

```
bunker list --server bunker-mvp --status all
  → 4 agents: 67aeb9f5 (10:20:30Z), cf-node, ci-e2e-01, a8354993 (10:02:50Z)
```

Agent `51fa2112` (this tick's rejected adversarial cell) is **absent**. The four survivors
belong to other lanes and were not touched. No local daemon started this fire; no port held.

## 3. Deferred item: pending-row premises — true at `cbbfe42`, VOID at `8c8097e`

At `cbbfe42` the answer was clean: `git diff --name-only 489bbd4..HEAD` contained no product
source, so every behavior measured at the pin still described HEAD and no arm needed
re-running.

That is **no longer the case at the new HEAD**:

```
git diff --name-only 489bbd4..HEAD | grep -vE '^(\.coding-hermes/|docs/|skills/|\.gitreins/)'
  plugin/terminal_jail/_bundled/terminal-jail
  plugin/test_tjdf047_fs_degrade_plain_allow.py
  standalone/terminal-jail
```

So this fire stopped inheriting and re-probed the one product claim that moved (section 5),
and re-timed the checkout build (section 8). The other pending rows were not re-driven:
their code paths are untouched by those three files.

Board census at `8c8097e` — 392 rows, all seven still **pending**:

| row | status | priority |
|---|---|---|
| `TJ-DF-064` | pending | P1 |
| `TJ-DF-065` | pending | P3 |
| `TJ-DF-066` | pending | P2 |
| `QA-TERMINAL-JAIL-11` | pending | P3 |
| `QA-TERMINAL-JAIL-19-R2` | pending | P2 |
| `QA-TERMINAL-JAIL-32` | pending | P3 |
| `OPS-TJ-001` | pending | P2 |

`TJ-DF-064-R2` exists only in `.gitreins/tasks.yaml` (sibling judge task, status `complete`);
the board carries no row for it (`grep -c` → 0 in both `tasks.jsonl` and `events.jsonl`), so
the board census is not missing a row.

`boardctl -C /home/kara/terminal-jail validate` → `RESULT: OK (303 warning(s))`, **0 errors**;
the warnings are the standing legacy duplicate-event-id / legacy-shape class (`events.jsonl
line 797: duplicate event id 401`, …), none naming a row from this tick, and the 303 count is
identical to fire 2's grade — nothing drifted between fires.

## 4. Preserved evidence re-verified against the agent-side claim

```
sha256sum /home/kara/.hermes/cache/scratch/tj-battery-51fa2112.jsonl
  ddb3f6424fe507d6d7c97be4ee5072bf30f1334c0082150130a84ae18e1f4279   24 lines
```

That is the **complete** 24-cell agent-side ledger fire 2 quoted, not the 9-record
collector-side `/tmp/bunker-qa-evidence-20261114T101500Z-2836405.jsonl` (`fd7ab5f8…`). The
truncation was a collector artifact and the proof of it survived the teardown.

Committed artifacts present in HEAD: `docs/dogfood/2026-11-14-install-battery-ledger.md`,
`docs/dogfood/2026-11-14-deny-by-default-and-a-dead-rule.md`, `docs/dogfood/diagnostics.md`,
`skills/terminal-jail-usage/SKILL.md`.

## 5. `TJ-DF-064` — upgraded: the code half is FIXED ON MAIN and verified live; a host reinstall is all that is left

Fire 1 graded this P1 as "fix `ae8524e` is in HEAD, the host install predates it → deploy
note". The deploy note reproduces exactly on the installed build:

```
/home/kara/.local/bin/terminal-jail --version        → terminal-jail 1.3.3  (mtime 2026-11-10 05:13)
env -u TERMINAL_JAIL_LANDLOCK … echo tj-064-probe    → rc=0, stdout "tj-064-probe"
    stderr: "WARNING: Landlock filesystem tier not applied (landlock-loader.py is not
             reachable by the launch's payload uid … commands run unchanged without kernel
             filesystem enforcement …)"
```

But the sibling's four commits are a **different, newer fix**, and it is now on `main`.
Probed against the checkout build at `8c8097e`, same canary, same minute:

```
./standalone/terminal-jail echo tj-064-head          → rc=0, no warning in stderr (grep -c → 0)
./standalone/terminal-jail cat $CANARY (tier on)     → "cat: …: Permission denied"  rc=1
TERMINAL_JAIL_LANDLOCK=0 … cat $CANARY (tier off)    → TIER-CANARY                  rc=0
host head -c 40 $CANARY                              → TIER-CANARY   (file is readable outside the jail)
```

The three-way A/B is the load-bearing part: the warning is **gone while enforcement is still
real**. That is the failure mode worth naming — suppressing an alarm by disabling the
protection underneath it would have looked identical at the stderr level and been caught only
by the `rc=1` / `rc=0` pair. It was not that. `git merge-base --is-ancestor ae8524e HEAD` → yes.

Grading: the code half of `TJ-DF-064` is fixed and CI-green at `8c8097e`; the **only** remaining
user-visible symptom is on the host, because the installed binary is still the 2026-11-10 build.
Re-running `install.sh` closes it. The row is left `pending` to its owner — this lane files and
verifies, it does not close rows.

## 6. Open boundary RESOLVED (negative): bunker-mvp has no tenant isolation

Both earlier fires carried `ISOLATION-UNVERIFIED`. The harness states the property outright,
for every agent on that host:

```
bunker list --server bunker-mvp --status all
  └ net: shared — host network namespace (no network isolation: shared loopback,
    global port space) — NOT tenant isolation     (all 4 agents, same line)
```

Grading: the `bunker-mvp` install leg proves **installability on a machine that has never seen
the project**; it can never prove tenant isolation, and no future fire should read it as if it
could. Host-tier property, not a product defect, and 42 board rows already mention isolation —
nothing filed.

## 7. Boundaries this fire could NOT close — stated, not papered over

- **PATH shadow, unverified.** Fire 1 found the real default UX on this host is *every command
  refused*, because `/tmp/tj-test-pack2/terminal-jail` (v1.2.0) sorted first on `PATH`. That
  shadow binary is still on disk (`/tmp/tj-test-pack2/terminal-jail`, 38401 B, mtime
  2026-10-01), but the login-shell `type -a terminal-jail` probe was **BLOCKED by the
  unattended tool-consent gate** (no answer = no consent) and was deliberately not retried
  through another command. PATH **order** therefore stays inherited-unverified from fire 1.
  Owner and root cause remain `OPS-TJ-001` (pending P2, owner-gated) — not re-filed.
- **True page-cache-cold timing** still unverified: dropping page cache needs root, which this
  lane does not have. Installed-CLI numbers are warm-state numbers and are labelled as such.
- **pipx channel** still unverified (unchanged from fire 2).
- **Shared-checkout collision**, disclosed in section 0, is a standing hazard rather than a
  one-off: my "premises still live" conclusion in section 3 expired within the hour. Board
  state and `main` must be re-read immediately before a closeout record is written, not at the
  start of the fire.

## 8. Performance (Step 2b): re-timed because the tree moved — no row

The "inherit the numbers" reasoning died with the `489bbd4..HEAD` diff, so the checkout build
was re-timed (`hyperfine --warmup 3 -r 15 --style basic`), and the installed binary's numbers stand
unchanged because that file was never rewritten (still the 2026-11-10 build).

| build / state | mean ± σ | runs |
|---|---|---|
| checkout CLI @ `8c8097e`, tier on | **256.6 ± 9.0 ms** | 15 |
| checkout CLI @ `489bbd4` (fire 1) | 242.8 ± 6.0 ms | 20 |
| installed CLI 1.3.3, tier on | 245.1 ± 7.8 ms | 20 |
| `TERMINAL_JAIL_LANDLOCK=0` | 178.0 ± 7.6 ms | 20 |
| `TERMINAL_JAIL_SANDBOX=off` | 250.2 ± 10.6 ms | 20 |

The checkout build is ~14 ms (~6%) slower than the pin. Two *separate* runs on a host with
sibling lanes compiling cannot attribute that to the three changed files; distinguishing it
would need a controlled A/B of both trees back to back. It is also well below anything a user
would feel for a single wrapped command. **No `PERF` row** — filing a 14 ms delta on an
uncontrolled comparison would devalue the real ones. The standing shape is unchanged: the fs
tier costs ~+67 ms (~+38%), sandbox-off saves nothing.
