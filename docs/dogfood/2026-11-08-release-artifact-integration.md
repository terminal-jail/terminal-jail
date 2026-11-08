# Dogfood run — 2026-11-08: the published v1.3.1 artifacts, used as a stranger would

Tick: `terminal-jail-dogfood-2026-11-08-04-02-17` · lane workdir `/home/kara/.hermes/stand-in/dogfood/terminal-jail`
Product checkout: `/home/kara/terminal-jail`, HEAD `516de67` (= `origin/main`, fast-forwarded after a
`git fetch`; the pre-tick checkout sat at `e35a4a1`, 5 board-only commits behind).
Published artifact: GitHub Release **v1.3.1** (`terminal-jail/terminal-jail`), published
2026-11-04T15:19:38Z, assets `SHA256SUMS` (196 B), `terminal_jail-1.3.1-py3-none-any.whl`
(190 931 B), `terminal_jail-1.3.1.tar.gz` (278 336 B) — all three downloaded and
`sha256sum -c SHA256SUMS` → both files `OK`.
Verdict: **PROMISING-BUT-ROUGH** — the source channel still works; the published release
artifact does not deliver what its own release notes say it does.

## Why this angle

The previous dogfood entry (2026-10-29, `docs/dogfood/2026-10-29-*.md`) closed on the resident
bridge and an unproven install leg. The product-surface delta since that HEAD is dominated by one
thing: **RELPKG-001** (`4843ffb`, "ship the standalone CLI and the Landlock loaders in the wheel"),
cut as **v1.3.1** with the changelog sentence *“so installing a wheel yields a working command and
live containment tiers.”* Nothing in `docs/dogfood/` had ever driven a **published wheel** as a
user would; the fix was verified by its own worker inside a fresh venv on the dev host. That is
exactly the surface a dogfood run exists to test.

## What a user is promised

| Source | Claim |
|---|---|
| `CHANGELOG.md` §1.3.1 (Fixed) | wheel install yields “a working command and live containment tiers”; `loader_path()` falls back to the bundled copy “so installing a wheel yields a working command and live containment tiers” |
| `docs/quickstart.md:50` | “A wheel built from a checkout is self-sufficient once installed (RELPKG-001): it provides the `terminal-jail` command and the Landlock/seccomp loaders” |
| `README.md:190` | release mode “is supported by `install.sh` via `TERMINAL_JAIL_USE_RELEASE=1` with `TERMINAL_JAIL_BASE_URL`, but no release assets are published yet” |
| `docs/quickstart.md:69-72` | release-mode downloads are “opt-in only … the installer refuses rather than hitting the dead default release URL” |

## What actually happened (every command run verbatim)

### A. Wheel install into a fresh venv (the artifact v1.3.1 exists for)

```
python3 -m venv venv-wheel
./venv-wheel/bin/pip install ./terminal_jail-1.3.1-py3-none-any.whl   # rc=0, PyYAML 6.0.3 pulled
./venv-wheel/bin/terminal-jail --version                              # terminal-jail 1.3.1, rc=0
./venv-wheel/bin/terminal-jail --help                                 # full usage, rc=0
```

The command exists and the seccomp tier works from the wheel:

```
./venv-wheel/bin/terminal-jail --seccomp grep Seccomp /proc/self/status
# Seccomp: 2   Seccomp_filters: 1        (host control: Seccomp: 0, filters: 0)
```

The interruptor engine is also fine **when the right interpreter reaches it** — driven directly,
the installed bridge returns a real verdict:

```
./venv-wheel/bin/python .../terminal_jail/interruptor_bridge.py < '{"command": "rm -rf /"}'
{"action": "block", "rule_id": "builtin-rm-rf-root", "reason": "Recursive root directory removal (rm -rf /) is blocked.", "layer": "yaml"}
```

### B. The same wheel, invoked the way a shim or a cron/agent does (absolute path, venv not on PATH)

```
$ ./venv-wheel/bin/terminal-jail echo hello-from-jail
{"ts":"...","event":"verdict","action":"block","rule_id":"[bridge-error]","layer":null,...}
+--------------------------------------------------------------+
|  COMMAND BLOCKED — [bridge-error]
|  [bridge-error] interruptor engine not importable — fail-closed: blocking command (enforce mode)
|  Command: 'echo' 'hello-from-jail'
rc=126
```

Every command in the default (firewall-on) mode is blocked. `--no-interruptor echo hi-no-fw` → rc=0,
so the jail itself is healthy; it is the firewall leg that dies. Root cause, read from source:
`standalone/terminal-jail:321` runs the bridge as `python3 "$bridge"` — a **PATH-resolved**
interpreter — while `plugin/terminal_jail/cli.py` only exports `TERMINAL_JAIL_BRIDGE` and states in
its own docstring that this makes “interruptor mode … not depend on `python3` resolving the venv”.
It does. With `PATH=<venv>/bin:$PATH` the identical command returns
`{"action":"allow","rule_id":"allow-echo","layer":"yaml"}` and runs.

Which python3 was on PATH in the failing arm: `/home/kara/.hermes/installs/.../venv/bin/python3`
(a Hermes venv without `terminal_jail`); `importlib.util.find_spec("terminal_jail")` → `False`
there, `True` under the wheel's own interpreter. So the failure is “the executing interpreter
cannot import terminal_jail”, reported to the user as “interruptor engine not importable” with no
remedy hint.

### C. The Landlock tiers from the wheel — inert, on both tiers, proven by discrimination

```
# traversable prefix (0775, so the payload uid can reach the loader) — wheel install
$ PATH=$PWD/venv-wheel/bin:$PATH ./venv-wheel/bin/terminal-jail echo hi-layout
{"action":"allow","rule_id":"allow-echo","layer":"yaml"}
terminal-jail: proc_view=private (bwrap backend: fresh procfs via --proc /proc)
terminal-jail: WARNING: Landlock filesystem tier not applied (tier module not found next to the loader); running the command unchanged
hi-layout                                          rc=0
```

Same host, same command shape, **source** install (the documented channel) into a prefix of the
same permissions:

```
$ PATH=$PWD/src-home/.local/bin:$PATH src-home/.local/bin/terminal-jail echo hi-src
{"action":"allow","rule_id":"allow-echo","layer":"yaml"}
terminal-jail: proc_view=private (bwrap backend: fresh procfs via --proc /proc)
hi-src                                              rc=0        # no tier warning: the tier applied
```

Driving the two bundled loaders directly isolates the mechanism:

```
$ ./venv-wheel/bin/python .../_bundled/landlock-loader.py -- /bin/true
terminal-jail: WARNING: Landlock filesystem tier not applied (tier module not found next to the loader); running the command unchanged
$ TERMINAL_JAIL_LANDLOCK_NET=1 ./venv-wheel/bin/python .../_bundled/landlock-net-loader.py -- /bin/true
terminal-jail: WARNING: Landlock network (egress) tier not applied (tier module not found next to the loader); running the command unchanged
```

Cause, from `standalone/landlock-loader.py:43-65`: the loader walks UP from its own directory looking
for `plugin/terminal_jail/interruptor/landlock.py` or `<dir>/landlock.py`. In the wheel the loader
lives at `site-packages/terminal_jail/_bundled/landlock-loader.py` and the tier modules live at
`site-packages/terminal_jail/interruptor/landlock.py` / `landlock_net.py` — a sibling directory the
walk never visits. `loader_path()` (`interruptor/landlock.py:1180-1205`, the RELPKG-001 fix) finds
the **loader**; nothing can find the **module**. RELPKG-001 therefore closed on “the specific
warning is gone”, not on “the tier applies”, and both tier warnings are permanent for every pip
user.

An earlier arm of the same run, invoked from under `~/.hermes` (mode 0700), printed the *other*
degrade cause first — `landlock-loader.py is not reachable by the launch's payload uid (a parent …
lacks o+x)`. That is the known 0700-home class (TJ-DF-019 family), **not** this finding; the
traversable-prefix arm above removes it and the module-search warning still appears, which is what
pins the layout cause.

### D. Release-mode install against the project's own published release

```
$ HOME=<scratch> TERMINAL_JAIL_USE_RELEASE=1 bash /home/kara/terminal-jail/install.sh
terminal-jail installer: detected architecture x86_64
terminal-jail installer: installing v1.2.0...
terminal-jail installer: downloading v1.2.0...
curl: (22) The requested URL returned error: 404
rc=22

$ HOME=<scratch2> TERMINAL_JAIL_USE_RELEASE=1 TERMINAL_JAIL_VERSION=1.3.1 bash install.sh
terminal-jail installer: installing v1.3.1...
curl: (22) The requested URL returned error: 404
rc=22
```

The URLs `install.sh:1342-1343` builds are `${TERMINAL_JAIL_BASE_URL}/terminal-jail` and
`…/terminal-jail.sha256`. Against the real release:

```
…/releases/download/v1.3.1/terminal-jail           404
…/releases/download/v1.3.1/terminal-jail.sha256    404
…/releases/download/v1.3.1/terminal_jail-1.3.1-py3-none-any.whl   200
…/releases/download/v1.3.1/SHA256SUMS                             200
```

and the default `TERMINAL_JAIL_VERSION` is still `1.2.0` (`install.sh:21`) — the one tag whose
Release object carries **zero assets** (RELEASE-TJ-015). So the documented release path cannot
consume the project's own published artifacts under any spelling, and it dies with a bare
`curl: (22)` rather than a named cause. Two published releases (v1.3.0, v1.3.1) now falsify
README:190's “no release assets are published yet”.

### E. Supported channel control (source install at the published tip)

```
$ CI=true HOME=<scratch> TERMINAL_JAIL_INSTALL_DIR=<scratch>/.local/bin \
  TERMINAL_JAIL_RULES_DIR=<scratch>/.config/terminal-jail/rules.d \
  bash install.sh --no-path
terminal-jail installer: containment ceiling (Landlock): fs tier CAN engage and net (egress) tier CAN engage on this host (Landlock ABI 8 >= 4; opt in with TERMINAL_JAIL_LANDLOCK_NET=1)
terminal-jail installer: done.                     rc=0
```

So the promise holds on the channel the docs call supported; the failures above are specific to the
published wheel and to release mode.

## Performance (Step 2b) — measured, nothing to file

Headline operation: one wrapped command through the installed CLI (`terminal-jail echo hi`) — the
cost a user pays on **every** shell command. Paired in ONE hyperfine invocation, both arms with the
wheel venv on PATH, host loadavg 12.2-14.6 (16 cores):

| arm | mean ± σ | range | runs |
|---|---|---|---|
| wheel console script | 369.9 ms ± 46.6 ms | 330.7-520.4 ms | 20 |
| checkout CLI (`bash standalone/terminal-jail`) | 359.2 ms ± 47.9 ms | 286.7-506.7 ms | 20 |

Ratio 1.03 ± 0.19 — the wheel's python entry adds ~11 ms inside a ~360 ms floor that predates this
run (the wrapper floor and the fs-tier delta are already carried by TJ-DF-048). First invocation
after install: 0.32 s wall (`/usr/bin/time -p`). No profile was justified and **no PERF row was
filed**: nothing here is slow enough for a user to feel, and the interesting delta is ~10 ms.

Cold-boundary note: a true cold arm (dropped page cache) needs root and was not run; the 0.32 s
number above is a first-run-of-a-fresh-copy measurement with a warm page cache, labelled as such.

## Fresh-machine install leg (ephemeral bunker)

Host census first (`curl <url>/health`: 404 = alive, 000 = down): `bunker-las-02`, `bunker-mvp`,
`dedi-2`, `hermes4friends` alive; `bunker-las-01/03/04`, `cube-las-00`, `hermes-fleet-01..05`
down (000). Chosen host: **bunker-mvp** — `Status: ONLINE`, `/tmp: private (per-session
pam_namespace instance)`, **`Net mode: shared — host network namespace … NOT tenant isolation`**.
Per the procedure this grades the leg **install-proven / isolation-UNVERIFIED** (disqualifying
field: `Net mode: shared`), never an unqualified PASS.

```
BUNKER_QA_SERVER=bunker-mvp bunker-qa.sh launch /home/kara/terminal-jail
→ agent=2d6a3886 @ bunker-mvp (ttl 4h)   LAUNCHED, evidence=/tmp/bunker-qa-evidence-20261108T042052Z-3881271.jsonl
```

Cells observed (15 evidence rows synced while the battery was still running):

| cell | status | detail |
|---|---|---|
| toolchain-bootstrap ×7 | OK | go 1.27.3, python venv+pytest, gcc/g++, make, jq, docker compose/buildx, node v22.15.0 |
| fresh-install | **OK** | `Successfully installed PyYAML-6.0.3 terminal-jail-1.3.1` |
| lint | N/A | no supported lint trigger |
| tests | **FAIL** | `1 failed, 1920 passed, 65 skipped in 172.83s` |
| docker_build / compose_config | N/A | no Dockerfile / compose trigger |

The single test failure is `tests/test_composed_mode.py::TestCompositionBattery::test_live_three_cell_run`:
the composed-mode battery it shells out to reported `docker daemon unreachable: rc=1` and
`summary: 1/3 PASS, 2 UNAVAILABLE`. The guard above that test is
`shutil_which_docker()` = `shutil.which("docker") is not None` (`tests/test_composed_mode.py:326-329`,
used at `:436` with reason “docker not available on this host”) — it probes the **binary**, not the
daemon. Minutes later on the same agent `docker info` succeeds, so the daemon was reachable and the
fresh-machine red is a race the guard should have absorbed by skipping.

Battery not finished at the time of writing: `ci-pass` (act) still running, agent left intact by
`collect`. Install leg status: **install-proven / isolation-UNVERIFIED**, cells PARTIAL — no full
battery PASS is claimed.

## Findings filed

| Row | Sev | Subject |
|---|---|---|
| TJ-DF-060 | P1 | wheel-installed CLI: Landlock fs and net tiers are permanently inert — bundled loaders can't find their tier modules |
| TJ-DF-061 | P2 | wheel-installed CLI: default mode blocks every command with `[bridge-error]` when the installing venv isn't first on PATH |
| TJ-DF-062 | P2 | release mode can't consume the project's own published assets (`terminal-jail`/`.sha256` 404), default version names the assetless tag, docs still say “no assets published” |
| TJ-DF-063 | P2 | fresh-machine suite red: composed-mode cell's precondition guard checks the docker binary, not the daemon |

## What was NOT proven

- The battery's `ci-pass` (act) and later cells — still running when the tick closed.
- A kernel-denial demonstration of the fs tier on the wheel arm (the command shape was refused by
  the harness gate; the loader warning + layout + source-arm discrimination carry the finding).
- `pipx` specifically (not installed on this host); the failing arm is the same mechanism
  (console script invoked outside an activated venv, PATH python3 that cannot import terminal_jail).
- True cold (page-cache-dropped) timing.
