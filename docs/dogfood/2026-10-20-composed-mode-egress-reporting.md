# terminal-jail — dogfood run 21: composed mode, the degrade arms, and the fresh-box install leg

- **Date:** 2026-10-20 (tick `terminal-jail-dogfood-2026-10-20-01-38-39`)
- **HEAD:** `2177a3c` at tick start, `319e02b` (origin/main, after the sibling run-20 commits landed in the shared checkout)
- **Verdict:** 🟡 PROMISING-BUT-ROUGH — the TJ-DF-046/047 fixes hold on the plain-allow path and on the installed CLI; the COMPOSED launch shape reports the egress tier in two contradictory ways in one run.
- **Angle:** the launch shapes and arms no prior entry drove — composed mode on a fresh 0750-home box, the four loader-degrade arms, the knob spelling matrix, the install containment-ceiling arms, and the installed-CLI parity of the new tier.
- **New row:** `TJ-DF-051` (P2). **Re-proofs:** `TJ-DF-049` (event 689), `INT-CI-009` recurrence (event 690). No PERF row (numbers below; nothing user-noticeable).

## Promise (null hypothesis)

`terminal-jail` claims (README.md:308-317, :450-451, :70-77): with
`TERMINAL_JAIL_LANDLOCK_NET=1`, **every** `connect(2)` to a TCP port outside the
allowlist fails EPERM/EACCES **at the kernel**, in the payload and every
descendant, **even when the command matches no egress regex** — and a payload is
never *silently* left with egress unchanged: every non-attach outcome prints one
loud `WARNING: Landlock network (egress) tier not applied (<cause>)` naming why,
**on the plain-allow path exactly as on the auto-sandbox path** (TJ-DF-046/047).

## What was driven (control host: kernel 7.0.0-38, Landlock ABI 8, HOME mode 751; fresh box: bunker-mvp agent `e7f7ce38`, kernel 6.8.0-142, ABI 4, HOME mode 750)

| Leg | Shape | Observed |
|---|---|---|
| P1 | plain-allow (`python3 -c`), tier ON, port 19099 | verdict `allow/rule_id:null` + `APPLIED` + `errno=13 EACCES` — **the TJ-DF-046 fix holds** |
| P2/P9 | allowlisted 9999; explicit `ALLOW=''` | `CONNECTED`; deny-ALL → `errno=13` |
| P5/P7 | `--user`; `bwrap` backend | tier attaches (named fs-isolation cause + `APPLIED`) |
| C1/C2 | forked child; exec'd descendant | both denied `errno=13` (payload+descendants covered) |
| C6/C7 | real workflow: `git ls-remote` over 443 | works under the tier; with `ALLOW=''` fails at the kernel (`Could not connect … after 1 ms`) |
| C3/C4 | `TERMINAL_JAIL_JAIL_BACKEND=unshare` | rc=2 `namespace creation failed` **with the tier off too** → host limitation, not the tier |
| D2/D3/I4 | `--seccomp`; `--user --seccomp`; installed-CLI `--seccomp` | tier still attached |
| A1/A2/A3 | loader **missing** / **unreadable** / control | exactly one named-cause line each (`… not found (searched …)` / `… cannot read …`), payload still runs; control `APPLIED` |
| D4/D5/D6 | same arms via a scratch copy of `standalone/` | blocked by `interruptor-bridge-unavailable` (the copy has no `../plugin` tree) — drive these arms with `TERMINAL_JAIL_LANDLOCK_NET_LOADER` or `TERMINAL_JAIL_BRIDGE` instead |
| K1-K14 | knob spellings | `true/TRUE/Yes/ON/1/yes/on` attach; `0/false/no/off/2/garbage/" 1"` stay off **silently** (documented at README:450 — not filed, but a footgun) |
| I1-I3 | install.sh → scratch prefix, then the tier through the **installed** wrapper | `APPLIED` + `errno=13`; missing-loader degrade names the searched dirs — installed/checkout parity holds (the TJ-DF-044 class) |
| Probe-absent install | `scripts/landlock-capability-probe.py` removed | `fs tier CAN engage; net (egress) tier CANNOT (Landlock ABI 0 < 4 …)` on a host whose ABI is 8 → **TJ-DF-049 re-proved** (event 689) |

## The finding (row TJ-DF-051)

One composed launch on the fresh box prints, in one transcript:

```
terminal-jail: WARNING: Landlock filesystem tier not applied (layout refused); …
terminal-jail: WARNING: Landlock network (egress) tier not applied (landlock-net-loader.py is not reachable
  by the launch's payload uid (a parent of /home/bunker-e7f7ce38/.local/lib/terminal-jail/landlock-net-loader.py
  lacks o+x — e.g. a 0700/0750 home)); commands run with network egress unchanged …
{"event":"verdict","action":"allow","rule_id":null,"layer":"engine"}
terminal-jail: COMPOSED MODE — running without an inner namespace
terminal-jail: composed layers — egress: enforced by terminal-jail (kernel Landlock TCP-connect allowlist; this tier needs no namespace)
terminal-jail: landlock-net: kernel egress tier APPLIED — TCP connect() restricted to ports [22, 53, 80, 443]; …
RESULT port=443 CONNECTED
RESULT port=19099 errno=13 Permission denied        <- the kernel really is denying
```

**Not applied** and **APPLIED** for the same launch. The applied half is the
truth (19099 → EACCES; with the knob off the same payload connects), so the
degrade line is a **false negative** the operator cannot distinguish from a real
one.

Mechanism: two attach decisions with different payload-uid assumptions.
`plugin/terminal_jail/interruptor/landlock_net.py:727-731` gates on
`_world_traversable` (`landlock.py:1201`), which demands `o+x` on **every**
ancestor because "a mapping-less rewrite runs its payload as nobody (65534)";
the composed attach (`standalone/terminal-jail`, `_tj_egress_tier_decide --here`)
probes in the composed launch's own context, where the payload runs as the
**owner** — it succeeds, the loader runs, and `APPLIED` prints. In composed mode
both decisions run for one launch and disagree. Reproduced in two layouts
(install.sh tree and a user-owned `~/n750` copy, mode 750), where the owner can
read the loader (`os.access R_OK = True`, `open()` ok).

Same root, second symptom: an invalid `TERMINAL_JAIL_LANDLOCK_NET_ALLOW` token
prints the refusal **twice** (wrapper: `probe crash: invalid … token 'bogus-port'`
then engine: `invalid allowlist token 'bogus-port'`).

## What did NOT reproduce (so nobody chases it)

- A 750 parent directory **alone** does not degrade the tier: the control-host
  A/B (parent 750 vs 755, plain bwrap launch) both printed `APPLIED` and no
  warning. The trigger is the composed/userns-less launch shape, not the mode.
- The fresh box's **plain** launch refuses entirely (`rc=2`,
  `namespace creation failed (unshare exit 1)` + the CAP_SYS_ADMIN/composed
  guidance) — honest, environment-caused: the bunker agent is a container.
- The `--user` and composed arms on the fresh box **do** apply the tier
  (19099 → `errno=13`), so containment is not lost — only the reporting.

## Install leg (fresh machine)

`bunker-qa.sh launch` is dead fleet-wide at this hour (empty battery, INT-CI-009
— my launch is the third recurrence, event 690; its refused launch leaves the
agent running, `27bb592f` destroyed by hand). The leg was therefore hand-walked
per the skill's generic ephemeral procedure on **bunker-mvp, agent `e7f7ce38`**,
TTL 1h, destroyed and verified gone:

```
clone https://github.com/terminal-jail/terminal-jail   rc=0, 1s
./install.sh --no-path                                 rc=0, 1s
terminal-jail --version                                terminal-jail 1.3.0
containment ceiling (Landlock): fs tier CAN engage and net (egress) tier CAN engage on this host (Landlock ABI 4 >= 4; …)
installed loaders: landlock-loader.py + landlock-net-loader.py present in the lib tree
```

## Performance (Step 2b) — no PERF row

Host load 24-25 (fleet crons); `hyperfine` is not installed, medians from
interleaved `date +%s%N` runs of the **installed** wrapper, same payload:

| Workload | tier ON | tier OFF | delta |
|---|---|---|---|
| `/usr/bin/true` (n=15) | 386 ms | 317 ms | ~69 ms |
| `python3 -c pass` (n=10) | 414 ms | 339 ms | ~75 ms |
| loader-seam attribution (n=6) | 62 ms (`python3 <net-loader> -- python3 -c pass`) | 17 ms bare | ~45 ms |
| `git ls-remote` over 443 (n=3) | 0.75-0.98 s | 0.60-0.61 s | network-dominated |

The egress tier costs ~45-75 ms per invocation on top of an existing ~300 ms
wrapper floor: **below the user-noticeable threshold**, and already covered by
`TJ-DF-048`'s tier-cost family. No profile was justified and no PERF row was
filed. (`fs`-tier ON/OFF was not measurable on this host: the fs tier degrades
here with "no caller-writable ungranted path for the enforcement probe".)

## Residual / unverified

- Composed-mode double reporting was **not reproduced on the control host** (its
  `TERMINAL_JAIL_COMPOSED=on` run took the normal bwrap path — composed mode
  engages only where the inner namespace cannot be created). The row's repro
  therefore names the fresh-box shape.
- `TERMINAL_JAIL_LANDLOCK_NET_ALLOW` service-name tokens (`https`, `domain`)
  were not driven against a privileged listener (unprivileged bind); port
  granularity was driven numerically instead.
- The two fresh-box transcripts were read over ssh while the agent was alive and
  are quoted verbatim here; the agent was then destroyed (archive on bunker-mvp).

---

## Second angle (run 21b, same tick): the documented audit tooling, and why the suite stayed green

After run 21 filed TJ-DF-051, the honest next question was not "drive one more feature"
but "why did a 2027-passing suite and two documented batteries not catch this?".

**Both documented batteries were driven and are honest.**

| Tool | Command | Result |
|---|---|---|
| live E2E firewall battery (README §Audit tooling) | `python3 scripts/e2e-battery-live-probe.py` | **rc=0, `LIVE-PROBE: 13/13 PASS`**, 14 PASS lines / 0 FAIL, wall **1352 ms**, empty stderr; positive control held (one allow WITH a rule id + one allow with `rule_id None`) |
| composed-stack battery (README:836, docs/composed-deployment.md:177,240) | `python3 scripts/composed-mode-battery.py` | **rc=0, `summary: 3/3 PASS, 0 UNAVAILABLE`** — cells carry raw properties (host: `proc_entry_count=1038`, `proc_1_comm=systemd`; platform/both: `proc_entry_count=1`, `seccomp_state=2`, `dockerenv=True`) and its own vocabulary refuses to convert an unmeasured cell into a pass |

Neither covers the surface TJ-DF-051 hits, and that is not a defect in either: the
E2E battery's pinned matrix is the *firewall verdict path* by its own docstring
(0 hits for `landlock|egress|composed|seccomp`), and the composed battery measures
per-layer properties (PID-ns inode, `/proc` counts, seccomp), not tier reporting.

**The coverage that was supposed to catch it cannot.** `plugin/test_tjdf046_egress_allow_path.py`'s
composed arm is the only cell pairing `TERMINAL_JAIL_COMPOSED=on` with
`TERMINAL_JAIL_LANDLOCK_NET=1`, and it ends with:

```python
if "COMPOSED MODE" not in result.stderr:
    pytest.skip("this host creates inner namespaces, so composed mode is unreachable here")
assert "tj-df-046-composed" in result.stdout, result.stderr
assert "egress: enforced by terminal-jail" in result.stderr or (
    "Landlock network (egress) tier not applied" in result.stderr
), result.stderr
```

1. The final `assert` is an **`or`**: a launch that prints *both* line families — the
   TJ-DF-051 state — satisfies it. A cell written to pin a mutually-exclusive contract
   must assert the *absence* of the other half.
2. The cell **skips** wherever composed mode is unreachable, i.e. on every host that can
   create an inner namespace (verified here: `TERMINAL_JAIL_COMPOSED=on` on the control
   host took the plain bwrap path and printed no `COMPOSED MODE` line), so on the dev
   host and on namespace-capable CI it asserts nothing and reads as green.
3. Where it *does* run, it drives the **checkout** loader (`standalone/…`, ancestors
   world-traversable on the dev host), so the engine's `_world_traversable` gate passes
   and the false degrade line cannot appear. The failing shape — loader behind a **0750**
   ancestor, which is Ubuntu's user-home default and the fleet's own bunker-agent default
   — is not exercised by any cell.

Filed as **TJ-DF-052 (P3)** with fix directions (assert the pair cannot co-occur; add a
0750-ancestor cell; make the skip visible), plus event 691 against TJ-DF-051.

**Not driven this angle (recorded so the next run can pick them):**
`scripts/backend-parity-battery.py`, `scripts/arg_size_benchmark.py`,
`scripts/kernel-matrix-teardown.py`; `gtfobins-sweep.py` and `rule-pack-tool.py` were
covered by runs 11 and 13.
