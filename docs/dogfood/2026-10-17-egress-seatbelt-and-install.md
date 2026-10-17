# Dogfood run 17 — 2026-10-17: egress tier real-use + install.sh skip ladder

Target: terminal-jail at HEAD `34b2bf0` (board: INT-CI-007 closed). Lane:
`terminal-jail-dogfood` (tick 2026-10-17-00-13-09). This run takes the angle
run 16 (10-13) left open: its unfiled egress-seam candidate, plus the
install.sh delta that landed since (`4dfad2f`, `cc3c664` — the
`--no-path`/CI/SUDO_USER/`/tmp` PATH-skip ladder and the test-env fixes that
made the CI legs green again).

## The promise under test this run

README section "TJ-GAP-083": with `TERMINAL_JAIL_LANDLOCK_NET=1`, "every
`connect(2)` to a TCP port outside the allowlist fails EPERM/EACCES at the
kernel — inside the payload and every descendant, exec/fork included — even
when the command string matches no egress regex (a raw
`python3 -c "socket...connect(...)"`, a tunnel's outbound leg)."

## 1. The egress tier driven as a real user

Fresh install of HEAD on the dev host (`/tmp/tjci…`, CI-shaped) and on a
fresh bunker-mvp agent (`df-tj-1017`), then driven through the INSTALLED CLI
as documented, with a live listener on 127.0.0.1:9999 (a non-allowlisted
port; default allowlist is 22,53,80,443).

| shape | tier | verdict observed | connected? |
|---|---|---|---|
| `python3 connect(9999)` through installed CLI (payload via file) | ON, default allowlist | `action=modify rule_id=auto-script` + loader degrade warning (0700 install home) | no (install-home shape) |
| same payload, real HOME (0755) | ON | `modify`, run unchanged per tenant | yes — see below |
| `python3 -c …` (README's literal example shape) | ON | `action=allow rule_id=null layer=engine` + **NO tier line** | **YES (CONNECTED)** — the promise does not hold on this shape |
| loader seam: `python3 landlock-net-loader.py -- python3 <payload>` | ON, default allowlist | `kernel egress tier APPLIED — restricted to [22,53,80,443]` | **no** — connect dies errno-13 EPERM |
| loader seam, `TERMINAL_JAIL_NET_ALLOW=9999` | ON | `APPLIED — restricted to [9999]` | **YES** (port allowlisted — correct) |

Read of the evidence: the tier ENGINE and LOADER are correct and live (the
kernel contract is exactly as documented at the loader seam). What fails is
launch wiring: `standalone/terminal-jail` attaches the FS Landlock loader on
all three exec paths (wrapper lines ~1175/1189/1206 — verified on checkout
AND installed copy), but the net tier only ever enters through the bridge's
modify-wrap prefix (`landlock_net_sandbox_prefix()`). An `allow` verdict —
which is precisely the regex-bypass shape the tier exists to catch — never
gets wrapped, gets no net loader, gets no warning, and connects.

Filed as **TJ-DF-046 (P1)** and **TJ-DF-047 (P2, warning-coverage half:
TJ-DF-044's fix ships the loaders now and warns on the modify path, but the
plain-allow path is still silent with tiers absent)**.

False-alarm notes (documented so the next run doesn't re-chase them):
- First CLI round took `rc=126` with no output — that was a 0700 scratch
  HOME (the documented TJ-DF-019/015 degrade, correct behavior, honest
  stderr once not truncated).
- One earlier probe killed the tier deliberately; ns-inode checks came from
  a different tier level. All contract legs above are from one pass.

## 2. Install.sh skip ladder (delta since run 16)

All on fresh scratch checkouts of HEAD `34b2bf0`, dev host:

| leg | env | rc | observed |
|---|---|---|---|
| CI-shaped fresh install | `CI=true`, scratch HOME, prefix under /tmp | 0 | skip notice "CI environment detected (CI=true)" in LOG (not rc), nothing written to rc, no stray rc files, installed `terminal-jail` reports `1.3.0` rc=0 |
| B: /tmp prefix skip | `CI,SUDO_USER,TEST` all unset | 0 | "skipping PATH setup — ephemeral install prefix", 0 rc-file markers |
| C: /tmp prefix + `TERMINAL_JAIL_TEST=1` | unset CI/SUDO_USER | 0 | correctly NOT skipped; non-default dir + no rc file → advisory "add this line", nothing written (contract: no rc file to append, no lie) |
| D: default scope + `TERMINAL_JAIL_TEST=1` | scratch HOME under /tmp | 0 | **classic block appended**: `# terminal-jail` + `export PATH="$HOME/.local/bin:$PATH"` in `.profile`, wrapper in `~/.local/bin`, `--version` 1.3.0 — the exact assertion the fixed CI test makes |
| E: `--no-path` | non-default prefix | 0 | "skipping PATH setup — --no-path flag", manual export line echoed, rc file untouched |
| F: `--no-path=1` | non-default prefix | **2** | "--no-path takes no value (it is a flag, not an option)", NOTHING written (no bin, no rc) |
| SUDO_USER | `SUDO_USER=dummy` | 0 | skip with named reason |

Plus the CI-equivalent pytest control under an env matching the GitHub
runner (`CI=true SUDO_USER= TERMINAL_JAIL_TEST=`):
`test_default_install_keeps_classic_path_behavior` **passed** (this was the
red test behind INT-CI-007), and the full `plugin/test_install.py` selection
**98/98 passed in 37s**. INT-CI-007's closure is locally reproducing at
HEAD. Caveat recorded in the log entry: the board row for INT-CI-007 closed
BEFORE its own CI run went green — cc3c664 itself is still red on GitHub
(run 38958973902; logs not downloadable without admin), HEAD 34b2bf0 is
green (38959902464) with no new fix in between that changes the tested
module. Signed-off-by-equivalent to: green at HEAD, red exactly one commit
back, no code between them — accept, but noted as an ordering nit, not a row.

## 3. Fresh-machine install leg (bunker, ephemeral)

Host: bunker-mvp (the only reachable bunker: las-01 offline 12d, las-02 4d,
las-03 12d, las-04 15d). Agent `df-tj-1017` (TTL 90m).

- https clone of the public origin: rc=0, **1s** (backend-parity: the fleet's
  checkout uses `git@github.com:terminal-jail/terminal-jail.git` — the https
  form works for everyone, including the agent).
- `sh install.sh`: rc=0, **1.0s**.
- `--version` → `terminal-jail 1.3.0`, rc=0.
- Tier report: pidns DEGRADED (container host), fs probe ran — this box is a
  userns-less container, which is exactly where the composed-mode story
  matters.
- Bare launch refuses with the documented named cause (no silent
  containment claim). `TERMINAL_JAIL_COMPOSED=on` → rc=0 with an honest
  "jail_layer=platform claimed… NO outer layer detected" line.
- Landlock loaders shipped: `landlock-loader.py` AND `landlock-net-loader.py`
  present in `~/.local/lib/terminal-jail/` — **TJ-DF-044's fix verified on a
  third install method** (run 16 proved the shipped tree on a different
  host; run 17 proves it end-to-end on the fresh-machine path).
- Default-scope PATH block appended to `~/.profile` (correct: no
  CI/SUDO_USER/`/tmp` conditions on the agent).
- Destroy: rc=0; residue recheck >90s later: 0 `df-tj-1017` users, 0 homes
  on the host. Clean.

## 4. Performance (Step 2b)

Headline operation = one wrapped invocation, warm. The host was under fleet
load the whole session (1-min loadavg 29–42), so all numbers are MEDIANS of
interleaved ON/OFF pairs (hyperfine sessions discarded for drift, then an
interleaved loop):

- CLI wrap, fs tier ON: **1036ms median** (n=12); OFF: 915ms; **delta +121ms**
- Second session (n=12, load 33): ON 1036 / OFF 915 → +121ms consistent
- Third session earlier (load 34): ON 633 / OFF 526 → +107ms
- Attribution: plain `python3 <payload>` ~69–92ms; `python3 landlock-loader
  -- <payload>` ~149ms; **tier cost itself ≈ +80ms**; remaining ~40ms
  wrapper/bwrap overhead variance.
- → **TJ-DF-048 (P2)**: the README's "Cost per verdict ~2ms engine +
  full interpreter start" row predates the tier's default-on (10-07) and is
  now stale; the honest number is ~+120ms per wrapped invocation on a
  mid-load box, and the suite's tier-OFF baseline (228–346ms on idle hosts)
  should be re-anchored on the release cut.

No flamegraph justified: nothing user-noticeable ON TOP OF the 650–1000ms
wrapper floor at this load, and the delta is a stable fixed cost, not a
per-frame hot path.

## 5. What a fresh user should know (this run's additions)

- Skipped-vs-silent PATH semantics are honest: on CI/sudo/`/tmp`-prefix
  installs you get an explicit notice in the INSTALL LOG, not in your rc
  file; `--no-path` is fully silent except the notice + manual line.
- On a userns-less container the fresh install is deliberately NOT
  containment-complete: pidns tier reports DEGRADED, bare launch refuses
  with an actionable cause, and composed mode is the documented path.
- The net-tier README guarantee currently depends on the command string
  matching a rule (TJ-DF-046, pending foreman fix) — verify egress with the
  loader seam, not through the CLI, until that lands.
