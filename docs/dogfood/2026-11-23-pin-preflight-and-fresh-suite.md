# Dogfood 2026-11-23 — pin-preflight gap, fresh-machine suite red, verdict-path A/B

Tick: `terminal-jail-dogfood-2026-11-23-18-36-23` (first delivery).
Product HEAD: `838a0d5f` (= origin/main, parity 0 0). Installed: terminal-jail 1.3.4 from the checkout into a scratch HOME (`/tmp/tj-df-20261123a/home`, `./install.sh --no-path`, rc=0, 0.95 s).

## What this run was

Angle: the user-visible fixes landed after the 2026-11-20 walk (TJ-DF-072/073 fixes,
TJ-REVIEW-076/077, README-016, PERF-005) driven from a fresh user seat, plus the
Step 2b perf measurement of the headline operation at HEAD. The release-install
branch was already walked earlier the same day (TJ-DF-075/076) and is not repeated here.

## Verdict: PROMISING-BUT-ROUGH

The core product holds and the four recent fixes all verify live. Two new
defects were found and filed (TJ-DF-077, TJ-DF-078). Details below.

## Holds — verified live (installed 1.3.4, scratch HOME, bwrap backend)

| Surface | Result |
|---|---|
| `--version` | `terminal-jail 1.3.4` rc=0 |
| PID-ns containment | host `pid:[4026531836]` vs jail `pid:[4026534056]`, `proc_view=private` |
| Verdict provenance | echo → `allow / allow-echo / layer=yaml` with command_sha256 |
| TJ-DF-073 fix | broken pin (`TERMINAL_JAIL_PYTHON=/nope/python3`) → the **interpreter-unavailable** box (not bridge-unavailable), rc=126, "Refused before the command-firewall evaluation" |
| TJ-REVIEW-076 fix | modify + `TERMINAL_JAIL_LANDLOCK_NET=1` + pin under a coverable interpreter → fs AND net tiers APPLIED, `make` payload ran, rc=0 |
| TJ-REVIEW-077 fix | ambient-PATH modify (un-coverable interpreter) → named refusal rc=2 with the NEW grant-coverage remedy wording ("an absolute path alone is not the criterion…") |
| README-016 | net tier on, unallowlisted port → `DENIED errno=13 (EACCES)`; control (net off) → `ECONNREFUSED`. Matches the corrected doc wording. |

## New findings

### TJ-DF-077 (P2) — the pin satisfies the preflight; the payload still dies raw

Following the product's own remedy (set `TERMINAL_JAIL_PYTHON` to a coverable
interpreter) on a host whose ambient PATH python3 is un-coverable (this host:
harness venv python3 under `/home/kara/.hermes/installs/...`):

- pin + tiers on → `auto-script modify` verdict prints, tiers APPLIED, then RAW
  `Fatal Python error: Failed to import encodings module`, rc=1, **no
  terminal-jail named-cause line**.
- Same arm, tiers off → payload runs and prints
  `EXECUTABLE=/home/kara/.hermes/installs/.../venv/bin/python3` — the pin covered
  the loader heads, **not the payload's own argv[0]**, which resolved via PATH
  inside the sandbox.
- fs tier on / net off reproduces the death (fs grant is the denier); clean PATH
  without the pin runs fine (ECONNREFUSED rc=0; with net tier: EACCES).

The pin-less ambient arm still refuses correctly with the named verdict — so the
pin-set shape slips past a check that exists. This is the failure class
TJ-REVIEW-074-R2 eliminated, reachable through the documented remedy.

### TJ-DF-078 (P2) — fresh-machine suite red: fixed-name /tmp fixture, no teardown

`test_denied_read_is_eacces_inside_an_applying_child` (the f95ec9a0 TJ-DF-072
canary test) fails in **fixture setup** on bunker-las-02 at
`plugin/test_landlock.py:326` — `secret.write_text()` on the FIXED path
`/tmp/secret600` raises PermissionError before any assertion. Proven on the agent:
`/tmp/secret600` is `-rw------- bunker-73676ddd` dated Nov 22 16:42 — a stale
fixture from yesterday's battery (the same id the launcher watchdog dropped as a
stale handle). bunker-las-02 has a HOST-SHARED /tmp, so the first uid to run the
test owns the file forever and every later agent uid reds the suite (tests,
ci-pass native, act, chaos-resource). Dev host passes (no stale file). The test
leaks the fixture: `secret600` has no unlink anywhere.

## Perf (Step 2b) — no PERF row, nothing user-noticeable

Paired A/B in ONE window (loadavg 48-49 on 16 cores), both from scratch-HOME
installs, warmup 3 × 15 runs:

- HEAD (838a0d5f, PERF-005 prefilters shipped): 352.1 ms ± 74.2 (min 288.1)
- control (195777fb^, pre-PERF-005): 370.8 ms ± 52.8 (min 291.9)
- ratio 1.05 ± 0.27 — the wrapped plain-allow path is unchanged by the
  prefilters (as expected; they target the blocklist eval) and sits at the
  recorded tier-on level (~350 ms).

An earlier single window at load ~45 read 608.3 ms ± 71.5 for HEAD alone —
discarded as load noise (the paired window is the evidence). Resident bridge
p50 9-29 ms (small/8K/20KB, n=30) — consistent with the README table.
`scripts/bench_bridge.py --n 30 --json` at HEAD is **VOID under load**: its own
TJ-GAP-084 cost guard fired (one-shot small p50 227.0 ms ≥ ceiling 200 ms,
rc=1) at loadavg 44.4 — quoted as the guard's own verdict, not a product
regression. PERF-005's AC-7 quiet-window (<8) re-measurement remains unmeasured:
the 15-min loadavg never dropped below ~35 all session (same boundary the perf
lane recorded across nine fires).

## Install leg — PASSED (not skipped)

- bunker-mvp: launch REFUSED by the launcher's own disk admission (97% > 94%).
- bunker-las-01/-03/-04, cube-las-00: OFFLINE.
- bunker-las-02 (ONLINE, bunderd 0.1.4, /tmp HOST-SHARED — caveats named):
  battery terminal, COLLECTED rows=24, fresh-install OK
  (`Successfully installed PyYAML-6.0.4 terminal-jail-1.3.4`), upgrade v1.3.3 →
  HEAD clean, chaos-errorpath OK, docker-deploy/chaos-shutdown SKIPPED by the
  controller-is-live-host safety gate, lint/docker_build/compose/ui-probe N/A.
  The four FAIL cells collapse to TJ-DF-078 (tests, ci-pass native+act,
  chaos-resource). Evidence: `.coding-hermes/evidence/qa-20261123T190946Z/`.
  ISOLATION caveat: Net mode shared — containment verdicts on that host are
  install-grade only. Agent b78c94b1 destroyed, `list` re-read = 0 agents, local
  key removed.

## Artifacts

- Evidence: `.coding-hermes/evidence/qa-20261123T190946Z/` (battery ledger +
  per-cell logs), `.coding-hermes/evidence/2026-11-23-pin-preflight/` (probe
  payloads + arm transcripts + ARMS.md).
- Board: TJ-DF-077, TJ-DF-078 (pending, one task_created event each).
- `docs/dogfood/diagnostics.md` §27, `skills/terminal-jail-usage/SKILL.md`
  pitfall, `.coding-hermes/dogfood-log.md` entry.

## Unverified this fire

- The pre-fix control binaries for TJ-REVIEW-076/077 were not rebuilt; the
  positive arms + the rows' judge evidence are cited instead of re-proving both
  directions.
- bench_bridge quiet-window numbers (load-bound all session).
- bunker-mvp disk trend (its 92%→97% move in minutes is an infra finding for the
  host owner, not this product).
