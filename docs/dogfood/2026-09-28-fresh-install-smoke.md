# Dogfood run 12 — 2026-09-28: fresh-machine install + smoke (returning angle)

**Lane:** terminal-jail-dogfood · **Workdir:** /home/kara/terminal-jail · HEAD 14a6f46

## Why this angle

Runs 1-11 covered CLI, packs, plugin+seccomp, library bridge, deploy shim,
systemd probe, operator tooling. The recurring full-battery QA tick
(QA-TERMINAL-JAIL-13, see HEAD commit) re-verifies the battery; this run went
back to the plainest real-user question — *can a stranger clone, install, and
get contained in one sitting on a fresh Debian box* — because the last three
fresh-install legs each hit something (TJ-DF-024/025 aborted installs,
TJ-DF-027 kernel-matrix failure) and never yet produced a fully green
clone→install→smoke→pack attempt in one pass.

## The run (bunker-las-03, agent 875dedf2, destroyed)

| Step | Result | Time |
|---|---|---|
| `git clone` (public GitHub origin, from README) | OK, HEAD 14a6f46 | 4s |
| `./install.sh` (bare, documented) | OK, wrapper + bridge + seccomp loader + rules mirror | <1s |
| `terminal-jail --version` | `terminal-jail 1.2.0` | instant |
| `python3 scripts/pidns-capability-probe.py` | `FULL` | instant |
| jail pid inode ≠ host inode | `pid:[4026531836]` → `pid:[4026533780]` | — |
| `--user` identity scrub | `nobody nobody /nonexistent` | — |
| firewall block `rm -rf /` | `COMMAND BLOCKED — builtin-rm-rf-root`, rc=126 | — |
| auto-sandbox modify (`python3 /tmp/mk.py`) | `Modified: … → sandboxed`, rc=0 | — |
| allow with provenance (`git status`) | runs, clean | — |
| `--list-rule-packs` on PyYAML-less host | reports `db: unreadable (…PyYAML is not installed…)` | rc=0 |
| `./install.sh --rule-pack db` on PyYAML-less host | clean SKIP + summary, base install completed | rc=2 |
| `rules-drift-probe.py` on PyYAML-less host | WARNING unparseable mirror + `drift=0` | rc=0 |

This is the first fresh-machine run where the documented FULL-branch smoke
passes end-to-end with zero guesswork: TJ-DF-024/025 (abort-on-pack,
--list-rule-packs poisoning &&-chains) are fixed — the pack path now skips
cleanly with a printed reason instead of killing the install.

## Findings

### TJ-DF-038 (P2) — PyYAML-less host: the user rules mirror is silently inert and the drift probe still says drift=0

On the fresh Debian agent (no python3-yaml, PEP 668 blocks pip):

- The engine reads `~/.config/terminal-jail/rules.d/00-builtins.yaml` with
  PyYAML; without it the rule file **fails open** — the built-in Python rule
  set keeps working, but any user override/addition in the mirror never
  loads, with no verdict-time message.
- `scripts/rules-drift-probe.py` prints exactly one line:
  `WARNING: unparseable rule file (engine fails open): …/00-builtins.yaml`
  and then `RESULT: drift=0 …`, **exit 0**. A user who added a host rule and
  runs the probe gets a green result on a host where the rule never fired.
- The install-time pack skip IS honest now (printed skip + rc=2 summary) —
  the gap is only the runtime mirror path and the probe's exit policy.

Fix direction: the drift probe should either fail on drift (its
`--fail-on-drift` mode already exists) classify "unparseable mirror" as a
drift-class condition with a remediation line (`apt install python3-yaml`),
or the wrapper should warn once at verdict time when the mirror cannot be
parsed. Related history: DF-21 (abort → now clean skip), DF-22 (prefix
installs write where the engine never reads).

## What worked without friction (worth keeping)

- Quickstart §3a FULL branch reproduces verbatim on a fresh host.
- Verify examples state the right invariant ("different inode = containment,
  rc=0 proves nothing") — the #1 mistake a new user would make is pre-empted
  in the docs themselves.
- `--user` identity scrub and auto-sandbox modify both work out of the box.

## Perf

`hyperfine --warmup 3 --runs 20 'terminal-jail sh -c "readlink /proc/self/ns/pid"'`
→ **197.5 ms ± 15.3 ms** (dev host, warm); cold one-shot 0.196s `time -p`.
Consistent with runs 9-11 (~185-215 ms). Nothing user-noticeable → no PERF row.

## Install leg

Not SKIPPED — executed: clone 4s + install <1s + smoke PASS on
bunker-las-03 agent 875dedf2 (destroyed, verified gone). Fresh-machine rule
pack leg exercised in the same session (skip path, see TJ-DF-038).
