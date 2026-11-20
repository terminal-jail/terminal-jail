# Dogfood 2026-11-20 — the interpreter-resolution contract, driven as a stranger

Tick: `terminal-jail-dogfood-2026-11-20-15-00-01` (first delivery; gateway count = 1)
Target HEAD: `e67e07e` (= origin/main at fire start, `git rev-list --left-right --count HEAD...origin/main` = `0 0`)
Product under test: v1.3.4, fresh `./install.sh --no-path` installs into TWO throwaway
HOMEs (`/tmp/tj-df-1120/home-a`, `/home/kara/tj-df-1120/home-b`), installed CLI driven
with a clean `PATH=/usr/local/bin:/usr/bin:/bin`.
Host: kernel 7.0.0-43-generic, 16 cores, loadavg 28-44 during the run (all wall times
are load-inflated; CPU time quoted beside the headline numbers).

## Why this surface

Everything that landed between the 2026-11-17 walk and this tick is one feature family:
**the interpreter-resolution contract** — `RELEASE-TJ-021` (in-jail trampolines splice
`$_TJ_BRIDGE_PY`, broken-pin refusal), `TJ-REVIEW-074-R2` (the modify path names the
unreachable interpreter instead of leaking `rc=126`), plus the `TJ-DF-071` unzip
test-host fix and the `TJ-REVIEW-072-R2` version-literal fix. None of it had been
driven by a real user. The promise under test (README "Graceful degradation", :842,
and specs/cli.md §3):

> An explicitly set but unexecutable `TERMINAL_JAIL_PYTHON` is refused before the
> launch (exit 126, `interpreter-unavailable`, naming the path and the cause —
> missing / not-executable / not-on-PATH) instead of an unexplained 127 or a silent
> fallback to PATH's `python3`.
>
> When the Landlock tier applies and the rewrite's head interpreter cannot start
> **under the tier**, the launch exits 2 with `auto-sandbox modify unavailable (…)`
> naming the interpreter and stating the command was not run. Remedies: pin
> `/usr/bin/python3` or set `TERMINAL_JAIL_LANDLOCK=0`.

## Install + time-to-first-success (local leg)

- `install.sh --help` rc=0 in 0.01 s, no filesystem writes (documented contract holds).
- Fresh install rc=0 in **3.60 s wall** (0.45 u + 0.23 s sys); wrapper 1.3.4; the
  containment-ceiling report printed `fs tier CAN engage and net (egress) tier CAN
  engage (Landlock ABI 8 >= 4)`, fs-isolation probe `DEGRADED` (see host-class note).
- First verdict (`terminal-jail /bin/echo …`): rc=0, payload ran, JSON verdict event
  with rule provenance + `proc_view=private (bwrap)` on stderr, 0.97 s wall (first,
  cold-ish). No blocker, no undocumented flag needed anywhere. Friction count: 2
  (both are the findings below).

## What holds (verified live)

| Contract | Arms | Result |
|---|---|---|
| Broken pin refused before launch, payload never runs | a3 (missing), a4 (not-executable), a5 (bare not-on-PATH) | rc=126 each, stdout empty each, fault reason named each (`no such file` / `not executable` / `not on PATH`), no silent fallback |
| Warn mode degrades loudly and runs | a6 | rc=0, payload ran, WARNING chain naming the pin fault + warn-mode fallback |
| Empty/unset pin keeps historical `python3` | a8 | rc=0 |
| Firewall alive at this install | a9 | `rm -rf /` → rc=126 `builtin-rm-rf-root`, verdict JSON `layer: yaml` |
| **TJ-REVIEW-074-R2 fix (the flagship repro)** | f1 | `make ok` with a REAL-FILE python3 under `<home>/.hermes/bin` first on PATH → **rc=2, stdout empty, one named verdict**: `auto-sandbox modify unavailable (the rewrite's payload starts with the interpreter 'python3' (/…/.hermes/bin/python3), which the filesystem tier's Landlock domain cannot execute for 'make'; command not run — … point TERMINAL_JAIL_PYTHON … or set TERMINAL_JAIL_LANDLOCK=0 …)` |
| Both documented remedies for that refusal | f2 (pin `/usr/bin/python3`), f3 (`LANDLOCK=0`) | rc=0, `MODIFY-PAYLOAD-RAN` both |
| Symlink into a granted tree is not refused | f4 | python3 → `/usr/bin/python3` symlink runs (target granted; Landlock resolves the final inode) |
| v1.3.0 literals gone (TJ-REVIEW-072-R2) | grep + banner | 0 hits in `plugin/__init__.py`, `plugin/terminal_jail/__init__.py`, `scripts/metrics-export.py`; `--version` → 1.3.4 |

The 2026-11-14 symptom (rc=126, empty stdout, success-shaped verdict, raw
`bash: … Permission denied` leak, no named cause) is **gone** in the flagship shape.

## Finding 1 — TJ-DF-072 (P2): the fs tier's in-launch warning contradicts the delivered containment

The canary pair, one variable at a time (`make canary` = `cat` of a mode-600 file at
`/run/user/1000/tj-canary`, a path the tier layout never grants):

- `terminal-jail make canary` (default tier): **rc=2, `cat: /run/user/1000/tj-canary:
  Permission denied`** — the kernel enforced the allowlist inside the launch (e1, f5,
  two independent fresh installs).
- same + `TERMINAL_JAIL_LANDLOCK=0`: reads `SECRET-CANARY`, rc=0 (e2).

Yet every one of those tiered launches ALSO printed:

```
terminal-jail: WARNING: Landlock filesystem tier not applied (no caller-writable
ungranted path for the enforcement probe); commands run unchanged without kernel
filesystem enforcement — …
```

That sentence is **false for the launch it describes**: containment was delivered.
Mechanism: the tier trampoline applies the domain in the un-namespaced caller context
(standalone/terminal-jail:1330-1342 says this is deliberate — the loader's proof needs
a caller-owned ungranted probe path a nested `unshare --user` would hide behind the
overflow uid), and Landlock restrictions inherit across the namespace. The loader's
own SECOND attach inside the namespace then fails its probe and prints the
not-applied branch (standalone/landlock-loader.py:113-124). The fs tier has no
success twin of the net tier's `kernel egress tier APPLIED` line, so the only
operator-facing signal for a tiered launch is a warning asserting the opposite.
Filed as **TJ-DF-072**.

## Finding 2 — TJ-DF-073 (P3): a broken pin shows the WRONG refusal box

With the firewall ON (the default) and an explicitly broken pin, the user gets:

1. two raw bash exec-noise lines (`terminal-jail: line 348: <pin>: No such file or
   directory` / `Permission denied` / `command not found`) — the bridge exec failing
   inside the command substitution (standalone/terminal-jail:347-348);
2. the `COMMAND BLOCKED — interruptor-bridge-unavailable` box (:565) whose Fix text
   says `run ./install.sh from a checkout, or set TERMINAL_JAIL_BRIDGE` — the wrong
   remedy for a pin fault;
3. the honest one-line fault note naming pin + cause + "no silent fallback".

The documented `interpreter-unavailable` box (:392-414, specs/cli.md:404) fires only
from `_tj_require_interpreter` at :1404/:1582 — after a successful bridge verdict —
so when the PIN is what broke the bridge, that box is unreachable in the default
flow. rc=126, named cause, and payload-not-run all hold; the named SURFACE never
appears. Filed as **TJ-DF-073**.

## Rig lessons (for the next fire — these cost three invalid arm sets)

1. **A fake HOME under `/tmp` can NEVER exercise the credential-surface carve.**
   The tier's layout grants the kernel tmpdirs as WRITE roots
   (landlock.py `build_layout`, `drop_denied_tmp=True` default), so a hostile
   interpreter under `/tmp/<rig>/home/.hermes/...` is inside a granted ancestor
   (`hostile-covered-by: ['/tmp']` — measured with a layout dump) and the tier will
   happily execute it. Hostile trees must live under a real-HOME-shaped path outside
   the tmp grants (this run: `/home/kara/tj-df-1120/home-b`). This is why the first
   b/d arm sets showed the payload running "through" the tier.
2. **The hostile interpreter must be a REAL FILE named exactly `python3`.** A
   symlink resolves to its (granted) target — Landlock evaluates the final inode, so
   `python3 -> /usr/bin/python3` runs. The 2026-11-14 shape was a copied venv ELF.
3. **Composed mode is a namespace-FAILURE fallback** (specs/cli.md:278): on a host
   where namespaces still create (even degraded), `TERMINAL_JAIL_COMPOSED=on` is
   deliberately ignored (c1/c2 printed no composed banner). Don't use it to force
   the tier — the plain path already delivers it.

## Host-class observation (recorded, not filed)

Kernel 7.0.0-43 now denies `setgroups` inside unprivileged user namespaces
(AppArmor `unprivileged_userns`): the install summary prints fs-isolation `DEGRADED`
with the exact cause and the sysctl remedy, and the auto-sandbox runs the
mapping-less prefix (payload effective uid 65534). The product classifies this
honestly; nothing to fix in the product. Recorded because the 2026-11-17 entries
measured WORKING mapped launches on this host (kernel 7.0.0-38 then).

## Step 2b — performance

hyperfine warm, n=20 (n=10 modify), loadavg 28-33 on 16 cores — wall times are
host-inflated, min and CPU time quoted for stability:

| Operation | mean ± σ | min | user+sys |
|---|---|---|---|
| plain allow, tier ON (`/bin/true`) | 374.7 ± 67.1 ms | 289.6 ms | 178.0 + 52.9 ms |
| plain allow, tier OFF | 255.7 ± 133.6 ms | 174.2 ms | 157.3 + 43.7 ms |
| modify path (`make ok`, namespace + tier + proof) | 681.6 ± 230.3 ms | 442.6 ms | 334.6 + 131.4 ms |

Same order as every earlier fire (~250-306 ms warm floors, +62-75 ms tier delta).
The interpreter-resolution work adds no measurable wrapper cost when the pin is
unset (one env check), and the modify-path tier-head proof is one loader start
inside the 682 ms aggregate. **No PERF row** — nothing a user would feel beyond the
known tier cost; PERF-003 still owns the one-shot-allow residual.

## Verdict

**WORKS AS DOCUMENTED, with one lying warning and one wrong box.** The
interpreter-resolution contract holds end to end — pin enforcement, warn-mode
degradation, the named modify-path refusal and both remedies are kernel-real and
were re-proven live in the exact shape that failed on 2026-11-14. The two defects
are on the operator-facing surface (a warning that asserts the opposite of delivered
containment; a refusal box whose remedy text misattributes the fault), not in the
containment mechanism.

Evidence: `.coding-hermes/evidence/2026-11-20-interpreter-contract/` (probe scripts,
per-arm raw stdout/stderr, layout dump, INDEX.md). Board rows: TJ-DF-072, TJ-DF-073.
