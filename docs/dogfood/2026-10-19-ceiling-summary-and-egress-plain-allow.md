# Dogfood run 20 — 2026-10-19: install containment-ceiling summary + the plain-allow egress tier, driven for real

**Target:** terminal-jail @ `29ae69f3e6d8ddc9ce00b12fd15a74021ff0e021` (HEAD == origin/main)
**Angle:** first real use of the two commits that closed TJ-DF-046/047 — `7971495` (engage the Landlock
egress tier on plain-allow verdicts) and `9a5a642` ("install containment-ceiling summary + plain-allow
degrade contract"). Both rows read landed; no dogfood entry had ever driven the new doors.
**Verdict:** 🟡 PROMISING-BUT-ROUGH — the shipped contract holds on the plain-allow path and the new
install self-report works on the real host, but two arms of the promise do not match the code, and the
fresh-machine install leg could not use the fleet harness at all (see §5).

| | |
|---|---|
| Time-to-first-success | install 0.57 s (dev host) / 1.09 s (fresh box) + first wrapped command; first smoke within ~2 min |
| Friction count | 2 (harness render break; modify-path unattributed failure) |
| Facts proven live | ceiling line honest on a fresh install; plain-allow egress tier kernel-denies; four degrade arms name their cause |
| Rows filed | INT-CI-009 (P1), TJ-DF-049 (P2), TJ-DF-050 (P2) |
| PERF rows | none — measured, nothing user-noticeable (§4) |
| Install leg | PASS by the generic ephemeral procedure (agent `df-tj-1019` @ bunker-mvp, destroyed rc=0) |

---

## 1. The promise (null hypothesis)

*"An operator can install terminal-jail on a clean machine and be told, at install time, exactly which
kernel containment tiers that host can enforce; then every wrapped command either gets the opt-in
kernel TCP-connect deny or is told loudly why it did not."*

Two promises were under test, both shipped on 2026-10-18:

1. **README §Install, "Containment-ceiling summary (TJ-DF-047)"** — before `done.` every install prints
   one `containment ceiling (Landlock)` line with four arms (both/none/fs-only/`unknown`).
2. **README §Install, same block, run-time half** — "a payload is never silently left with network egress
   unchanged: every non-attach outcome prints `WARNING: Landlock network (egress) tier not applied
   (<cause>)` … on the plain-allow path exactly as on the auto-sandbox path (TJ-DF-046/047)".

## 2. What a real user got

### 2a. Install (documented path, scratch prefix, dev host)

```
$ TERMINAL_JAIL_INSTALL_DIR=/tmp/df-tj-1019/prefix ./install.sh        # rc=0, 0.57 s
terminal-jail installer: containment tier report (landlock-capability-probe):
Landlock capability probe: FULL
  ABI version (max supported): 8
terminal-jail installer: containment ceiling (Landlock): fs tier CAN engage and net (egress) tier CAN
engage on this host (Landlock ABI 8 >= 4; opt in with TERMINAL_JAIL_LANDLOCK_NET=1)
terminal-jail installer: done.
```

Honest and useful: the number (ABI 8) is the probe's own, and the run-time behaviour in the same session
matched it (§3). On a fresh bunker box (kernel 6.8.0-142, ABI 4 — exactly at the net tier's floor) the same
line printed with `ABI 4 >= 4` and was equally true.

### 2b. The degraded arms (scratch checkouts, nothing in the repo touched)

| installer arm | printed | verdict |
|---|---|---|
| real host probe (FULL, ABI 8) | `fs tier CAN engage and net (egress) tier CAN engage (ABI 8 >= 4 …)` | ✅ correct |
| stubbed `FULL`, ABI 3 | `fs tier CAN engage; net (egress) tier CANNOT (ABI 3 < 4 …)` | ✅ correct |
| stubbed `DEGRADED` | `NEITHER Landlock tier can engage … (the probe output above names the cause)` | ✅ correct |
| probe **absent from the source** | `fs tier CAN engage; net (egress) tier CANNOT (Landlock ABI 0 < 4 …)` | ❌ **fabricated** — the documented arm is `unknown`; no landlock classifier ran and no ABI was measured → **TJ-DF-049** |

Mechanism (bytes, not narrative): `install.sh:1542` seeds the summary from `TIER_FULL_OUT`, a variable the
tier-probe helper resets on every call (`:1455`, `:1466`) and whose last advisory-path writer is the **pidns**
probe (`:1504`) — the landlock probe is never routed through `run_tier_probe`, it only runs inside the
summary block (`:1549`) when its file exists. Probe absent → the guard short-circuits → `FULL` from the
pidns probe becomes the landlock verdict, the ABI grep finds nothing and forces `0`, and the `ABI<4`
branch (`:1576`) prints a ceiling claim the installer never measured. The `unknown` branch (`:1580`) is
dead code on any source that still runs the other probes.

### 2c. The run-time contract (fresh install of HEAD, dev host)

A live listener on non-allowlisted port 9999 and the README's own flagship shape (a raw interpreter
one-liner that matches no egress regex → `rule_id: null`, `action: allow`):

```
$ <prefix>/terminal-jail /usr/bin/python3 -c '<socket.create_connection(("127.0.0.1",9999))>'
  tier OFF (control): rule_id null -> CONNECTED ok data=b'pong\n'
  tier ON           : rule_id null -> BLOCKED PermissionError: [Errno 13] Permission denied
                      + "landlock-net: kernel egress tier APPLIED — TCP connect() restricted to ports
                         [22, 53, 80, 443]"
  tier ON + NET_ALLOW=9999 -> CONNECTED ok data=b'pong\n'  (banner names [9999])
```

**TJ-DF-046 is fixed.** The bug was: the tier rode only the auto-sandbox rewrite, so the documented
flagship launch ran CONNECTED. It now attaches on the plain-allow path and the kernel denies.

The same run drove every non-attach arm of the TJ-DF-047 contract on that path — each one named its cause
and ran the payload unchanged, never a silent CONNECTED:

```
(chmod 000 net loader)  -> WARNING: … (the payload cannot read …/landlock-net-loader.py in the launch that would run it)
(loader moved away)     -> WARNING: … (landlock-net-loader.py not found (searched <script dir> and <lib dir>))
(NET_ALLOW=not-a-port)  -> WARNING: … (invalid allowlist token 'not-a-port')   [plus the loader's own refusal line]
(parent dir not o+x)    -> WARNING: … (landlock-net-loader.py is not reachable by the launch's payload uid …)
```

### 2d. The auto-sandbox twin of that contract is missing (TJ-DF-050)

Same host, same session, same broken host state (`chmod 000` on the net loader), but a payload that the
engine classifies as `auto-script` (a **modify** verdict):

```
$ TERMINAL_JAIL_LANDLOCK_NET=1 <prefix>/terminal-jail /usr/bin/python3 /tmp/…/payload.py 9999
{"event":"verdict","action":"modify","rule_id":"auto-script"…}
[terminal-jail] Modified: '/usr/bin/python3' '/tmp/…/payl… → sandboxed
terminal-jail: WARNING: Landlock filesystem tier not applied (…)          <- fs tier only
python3: can't open file '…/lib/terminal-jail/landlock-net-loader.py': [Errno 13] Permission denied
rc=2
```

The command did not run, rc=2, and **no** `Landlock network (egress) tier not applied` line was printed —
the user sees a raw Python error. The plain-allow path on the *identical* host state degrades loudly
(§2c, arm 1). Mechanism: two different readability checks. The wrapper's plain-allow path probes
`test -r <loader>` under the launch it is about to run (`standalone/terminal-jail:1062`); the modify path's
tail is composed inside the engine (`decider.py:76` → `_wrap_payload`) behind
`landlock_net.py:727 _world_traversable()`, which walks only **ancestor directories'** `o+x`
(`landlock.py:1201`) and never the loader file's own read bits — so a path-traversable but unreadable
loader passes, gets spliced in, and the already-composed rewrite is exec'd with no preflight
(`standalone/terminal-jail:1271+`).

## 3. Fresh-machine install leg (ephemeral bunker)

**The fleet harness could not run it: `bunker-qa.sh launch` generates an empty battery and aborts after
spawning — filed as INT-CI-009 (P1).** Verbatim:

```
→ agent=1dd1f7eb @ bunker-mvp (tailscale)
/home/kara/.hermes/scripts/bunker-qa.sh: line 1061: UI_PORTS: unbound variable
ERROR: battery shipped EMPTY (~/qa-run.sh 0 bytes) on agent=1dd1f7eb (bunker-mvp) — script generation
failed; NOT launching (a 'LAUNCHED' over a dead battery misleads collect)
```

The render heredoc opens at `:1061`; the ui-probe block at `:2397-2407` references `$UI_PORTS`
**unescaped** while its siblings `:2424/:2436` correctly write `\$UI_PORTS`. A heredoc body expands at
render time, so `set -u` kills the `cat` on the first reference, the error is blamed on the heredoc open
line, and the freshly spawned agent is left behind (destroyed by hand, `1dd1f7eb`, ~8 min later).

So the leg was driven by hand per the skill's generic ephemeral procedure, on the same live host
(`bunker-mvp`, `bunkerd` active, listening on its tailnet IP):

| step | result |
|---|---|
| spawn | agent `df-tj-1019` @ bunker-mvp, TTL 2h |
| clone (documented https origin) | **rc=0, 2.08 s**, HEAD `2177a3cf189a1a6753d92fc134038bcbe85f8dcd` |
| `./install.sh` (documented, default prefix) | **rc=0, 1.09 s**; loaders + rules installed; PATH block appended to `~/.profile`; ceiling line printed for **ABI 4** |
| documented smokes | `--version` → `terminal-jail 1.3.0` rc=0; firewall bridge → `builtin-rm-rf-root` block rc=0; `scripts/landlock-capability-probe.py` → FULL/ABI 4 rc=0 |
| delta smoke (the fix under test) | tier ON plain-allow → connect **denied EPERM at the kernel** with the `APPLIED` banner; control and allowlisted arms reached TCP connect; three degrade arms printed their named cause |
| destroy | `bunker destroy df-tj-1019 --server bunker-mvp` rc=0, key removed |

Fresh-box findings that are **not** defects (documented behaviour, recorded so the next run does not
re-chase them):

- **Bare mode exits 2 on a stock Ubuntu-kernel box.** `./standalone/terminal-jail sh -c 'readlink /proc/self/ns/pid'`
  → `namespace creation failed (unshare exit 1)` + the named cause (AppArmor `unprivileged_userns`) + the
  `--user` / composed-mode remediation. README:249-251 documents exactly this, so it is honest — but it *is*
  the first command in the quickstart, so a fresh user's first experience is a refusal plus a hint. Drive
  `--user` (mapping-less) or composed mode on this class of host.
- **The launch shares the host network namespace** (`ip -o addr` inside the jail shows the host's `eth0`),
  consistent with README's "SANDBOXED — not network-contained".
- **A 0750 `$HOME` makes the tier loaders unreachable for the payload uid**, so on that class of box the
  fs/net tiers degrade loudly on every launch while the install summary says "CAN engage" (kernel-ceiling
  wording, not a launch-layout guarantee). The warning names the fix (`o+x` on the parents). Worth wording,
  not a row.

## 4. Cost (Step 2b, measured — and its honest verdict)

`hyperfine --warmup 3 --runs 15` on the fresh install, host load 12.9-17.5 on 16 cores (noisy — stddev is
large relative to the deltas, so read them as directions, not precision numbers):

| leg | mean ± σ |
|---|---|
| plain command, tier OFF | 305.6 ms ± 36.3 |
| plain command, tier ON | 367.8 ms ± 28.4 (**+62 ms**) |
| interpreter payload, tier OFF | 321.2 ms ± 25.2 |
| interpreter payload, tier ON | 390.1 ms ± 18.2 (**+69 ms**) |
| bare (unwrapped) `python3 -c 'import socket'` | 16.3 ms ± 1.4 |
| net loader alone on a trivial payload (seam attribution) | 47.2 ms ± 8.3 |

**No PERF row.** The net tier costs ~+60-70 ms per plain-allow invocation — one interpreter start at the
seam (47 ms measured directly) — on top of a ~300 ms wrapper floor. Sub-second, dominated by the floor:
not something a user would notice, so filing it would devalue the rows that matter. TJ-DF-048 already
carries the fs-tier delta and the stale README "Cost per verdict" note.

## 5. What was retracted (and why it matters that it was)

The first fresh-box delta leg printed a one-off `/usr/bin/python3: can't open file '<home>/payload.py':
[Errno 13] Permission denied` on the **modify** path. A mode bisect (600 vs 644) and four replays under
identical and varied conditions (same wrapper, `$HOME` payload, `/tmp` payload, tier on/off, loaders
readable/unreadable) all returned `PAYLOAD CONNECTED` — the reading did **not** reproduce, so it was
recorded as a leg artifact and **not** filed. Only the reproducible pair (leg D vs leg J, §2d) became a row.

## 6. Rows filed

| row | priority | summary |
|---|---|---|
| **INT-CI-009** | P1 | `bunker-qa.sh` renders an empty battery (unescaped `$UI_PORTS`, `set -u`) → every install-leg/QA battery dead fleet-wide; abort leaves the spawned agent behind |
| **TJ-DF-049** | P2 | installer ceiling summary prints a fabricated `ABI 0` + "fs tier CAN engage" when the landlock probe is absent; the documented `unknown` arm is unreachable |
| **TJ-DF-050** | P2 | modify path splices the net loader without a readability preflight → raw python `Errno 13`, rc=2, no named cause; plain-allow path degrades loudly on the identical state |

Events 686 (TJ-DF-046 re-proof) and 687 (TJ-DF-047 re-proof) carry the fresh evidence; both rows were left
byte-untouched, per the append-only rule.

## 7. Reproducing this run

```bash
# local real use
TERMINAL_JAIL_INSTALL_DIR=/tmp/df-tj-1019/prefix \
TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=/tmp/df-tj-1019/prefix/config/terminal-jail/rules.d \
  ./install.sh                                    # watch the containment-ceiling line
python3 -m http.server 9999 --bind 127.0.0.1 &    # a non-allowlisted live port
TERMINAL_JAIL_LANDLOCK_NET=1 <prefix>/terminal-jail \
  /usr/bin/python3 -c 'import socket; socket.create_connection(("127.0.0.1",9999),timeout=3)'
# expect: kernel EPERM + the APPLIED banner on the plain-allow path (TJ-DF-046 fixed)
# then: chmod 000 <lib>/landlock-net-loader.py and repeat with a SCRIPT payload -> TJ-DF-050
```
