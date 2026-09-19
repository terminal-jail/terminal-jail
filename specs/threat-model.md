# S07: Environment-Injection Threat Model — Layer-1 vs Wrapper Boundary

**Version:** 1.0.0
**Date:** 2026-09-19
**Status:** Accepted
**Task:** TJ-GAP-060
**Companion:** [docs/threat-model.md](../docs/threat-model.md) — the system-wide threat model (layers, actors, residual-risk matrix). This document covers ONE boundary in depth: environment-based attacks that the Layer-1 command firewall cannot see, and the wrapper-layer scrub that answers them.

## 1. Purpose

Terminal-jail's Layer-1 (the interruptor, S05) evaluates only the **command string**. An attack that lives entirely in the **process environment** — `LD_PRELOAD`, `BASH_ENV`, `PYTHONSTARTUP`, an imported bash function — executes attacker-controlled code without ever presenting a command to match. No rule engine that sees commands can ever catch these: this is a **structural layer boundary, not a missing rule**.

Env hygiene is therefore wrapper-layer responsibility. This document states the boundary honestly, defines the scrub the standalone wrapper (`standalone/terminal-jail`) performs, and lists exactly which variables are scrubbed, preserved, or not applicable per launch backend.

## 2. Why Layer-1 can never catch env-only attacks

```
attacker controls:  ENV(process env)                COMMAND STRING
                    │                                     │
                    ▼                                     ▼
             loader / interpreter                  interruptor rule engine
             honors hook BEFORE/AROUND             sees: "pytest" (benign)
             the payload; no command               verdict: ALLOW
             token represents it
```

Concrete mechanisms (all verified live on this repo's dev host, bash 5.3):

- **`LD_PRELOAD` / `LD_AUDIT`** — the dynamic loader preloads the named object into every subsequent process; code runs before `main()`, before any command exists.
- **`LD_LIBRARY_PATH` / `LD_DEBUG`** — redirects library resolution or turns loader debugging on (an information side channel and a load-time behavior changer).
- **`BASH_ENV`** — a **non-interactive** bash sources this file at startup before running any script. Measured: with `BASH_ENV` set, a plain `bash script.sh` executes the file first. This also applies to the wrapper's own payload trampoline (`bash -c …`/`bash -c 'exec …'`).
- **`ENV`** — the same class for POSIX-mode/`sh` startup.
- **`PYTHONSTARTUP` / `PYTHONPATH`** — interactive python startup execution / module shadowing. `PYTHONPATH` also shadows imports for the **interruptor bridge's python3** (which loads YAML rule packs), so it is an attack on the firewall tooling itself.
- **`PERL5OPT` / `PERL5LIB`, `RUBYOPT` / `RUBYLIB`, `NODE_OPTIONS`** — `-M` module loads / library paths / `--require` for their interpreters.
- **`GIT_EXEC_PATH`** — substitutes the git binary set.
- **`GEM_PATH` / `GEM_HOME`, `CPATH`, `C_INCLUDE_PATH`, `CPLUS_INCLUDE_PATH`, `OBJC_INCLUDE_PATH`** — package/library/include search hijacks (compile-time code injection).
- **Imported bash functions** (`BASH_FUNC_<name>%%=() {…}` via `env`/ssh, CVE-2014-6271 class) — a child bash imports these into its function table, where they can override expected tool behavior.

## 3. The wrapper scrub (TJ-GAP-060)

The wrapper performs a two-phase scrub in its preamble, **before backend selection, before the interruptor bridge is invoked, before the namespace preflights, and before every exec path** (bare, `--user`, `--seccomp` trampoline, bwrap, and the bridge's `python3`):

**Phase 1 — imported function sweep.** Runs before the wrapper defines any function of its own, so the function table contains only imported (hostile) definitions. Every imported name is `unset -f`'d. Measured mechanics this relies on: bash consumes the raw `BASH_FUNC_*` entry into its function table and removes it from `/proc/self/environ` (an env scan can never see it), and `unset -f <name>` (the name **without** the `%%` suffix) removes both the function **and** the raw exported entry — afterwards neither `env` nor a child shell sees any `BASH_FUNC_*` line.

**Phase 2 — hook-variable scrub.** Reads `/proc/self/environ` NUL-separated (byte-exact, newline-safe), and for each `NAME=value`: scrub hook variables (`unset -v`), keep control/passthrough variables unchanged, and re-export everything else so the child-visible value is the environment's value.

Ordering matters and is pinned by test: the function sweep must precede the re-export pass (a re-export while a same-named function exists would export the **function** form — bash: function > variable).

## 4. Audit matrix

Behavior is **backend-independent by construction** — the scrub runs in the wrapper preamble, before `TERMINAL_JAIL_JAIL_BACKEND` is read — and that ordering is pinned by `plugin/test_env_scrub.py::TestScrubPrecedesBackendSelection`. The matrix is still stated per backend, because the backends have different failure modes when the namespace itself is unavailable:

| Variable | Attack class | bare (unshare) | `--user` (mapped) | `--user` (degraded) | bwrap |
|---|---|---|---|---|---|
| `LD_PRELOAD` | loader code injection | scrubbed | scrubbed | scrubbed | scrubbed |
| `LD_LIBRARY_PATH` | library resolution hijack | scrubbed | scrubbed | scrubbed | scrubbed |
| `LD_AUDIT` | loader audit hook | scrubbed | scrubbed | scrubbed | scrubbed |
| `LD_DEBUG` | loader debug side channel | scrubbed | scrubbed | scrubbed | scrubbed |
| `BASH_ENV` | bash startup script exec | scrubbed | scrubbed | scrubbed | scrubbed |
| `ENV` | shell startup script exec | scrubbed | scrubbed | scrubbed | scrubbed |
| `PYTHONSTARTUP` | python startup exec | scrubbed | scrubbed | scrubbed | scrubbed |
| `PYTHONPATH` | module shadowing (incl. bridge YAML) | scrubbed | scrubbed | scrubbed | scrubbed |
| `PERL5OPT` / `PERL5LIB` | perl module load / path | scrubbed | scrubbed | scrubbed | scrubbed |
| `RUBYOPT` / `RUBYLIB` | ruby require / path | scrubbed | scrubbed | scrubbed | scrubbed |
| `NODE_OPTIONS` | node `--require` exec | scrubbed | scrubbed | scrubbed | scrubbed |
| `GIT_EXEC_PATH` | git binary substitution | scrubbed | scrubbed | scrubbed | scrubbed |
| `GEM_PATH` / `GEM_HOME` | gem shadowing | scrubbed | scrubbed | scrubbed | scrubbed |
| `CPATH` / `C_INCLUDE_PATH` / `CPLUS_INCLUDE_PATH` / `OBJC_INCLUDE_PATH` | compiler include injection | scrubbed | scrubbed | scrubbed | scrubbed |
| imported bash functions (`BASH_FUNC_*`) | CVE-2014-6271 class | swept (phase 1) | swept (phase 1) | swept (phase 1) | swept (phase 1) |
| `TERMINAL_JAIL_*` control vars | wrapper configuration | **preserved** | **preserved** | **preserved** | **preserved** |
| `PATH`, `HOME`†, `USER`†, `LOGNAME`†, `SHELL`, `PWD`, `SHLVL`, `LANG`, `LC_*`, `TMPDIR`, `TZ`, `OLDPWD` | benign passthrough | preserved | preserved | preserved | preserved |
| every other variable | benign passthrough | preserved (re-exported) | preserved (re-exported) | preserved (re-exported) | preserved (re-exported) |
| any variable, when the backend cannot launch | — | not applicable — fail-closed exit 2 (TJ-GAP-034), command never runs | not applicable — same exit-2 contract | warning + degraded launch, scrub still active | not applicable — fail-closed exit 2 (TJ-GAP-054) |

† On `--user`, `USER`/`LOGNAME`/`HOME` are additionally **overwritten** (`nobody`/`nobody`/`/nonexistent`) by the pre-existing identity scrub (TJ-DF-015) — unchanged by this task.

Values containing newlines survive byte-exact (NUL-separated read-back), and an imported-function name can never masquerade as a preserved variable: phase 1 empties the table before phase 2 runs.

## 5. Honest residual boundary

**The wrapper interpreter's own startup is NOT shielded, by mandate.** The wrapper's shebang must remain the literal `#!/usr/bin/env bash` — `install.sh`'s integrity check rejects any other first line — which forbids `bash -p`, the flag that suppresses `BASH_ENV`/`ENV` sourcing and `SHELLOPTS` import for the wrapper process itself (measured on bash 5.3; `--norc` does **not** suppress `BASH_ENV` for non-interactive scripts). Accepted residual: an attacker who can set `BASH_ENV`/`ENV` in the wrapper's inherited environment executes code in the **trusted wrapper interpreter** before its first statement. What the scrub guarantees is that **nothing the wrapper launches** — the payload, the interruptor bridge's `python3`, the namespace preflight probes, the seccomp loader — inherits the hostile variables. Changing the shebang (or a two-stage self-re-exec wrapper) requires an `install.sh` contract change and is deliberately out of scope for TJ-GAP-060.

Additional residuals:

- The scrub cannot protect launches that **bypass the wrapper** (plain shell, other tooling) — the same "CLI non-use" boundary as docs/threat-model.md §5.8.
- Variables not named in the hook list are passed through; the list is deliberately explicit (auditable, test-pinned) rather than an allowlist of the whole environment, because a whole-env allowlist breaks every legitimate tool's passthrough contract.
- Under a `-p`-style bash startup that skips function import entirely, bash quarantines the raw `BASH_FUNC_*` entry where no `unset` can reach it; that state is unreachable with the mandated shebang, and phase 2's scan covers the variable surface.

## 6. Verification (TJ-GAP-060 evidence)

`plugin/test_env_scrub.py` (new; 52 tests) pins the matrix:

- **Before-fix evidence:** launching the wrapper with all 14 hook variables set to marker values leaked **all 14 into the jailed payload env on every runnable backend** (`--user` and bwrap on the dev host), and an imported evil function survived (visible via `declare -F` in the payload).
- **After-fix:** every hook variable absent from the payload env, per-variable and in aggregate, on every backend that can run on the host; imported function swept; `TERMINAL_JAIL_*`/passthrough/multiline values preserved; scrub ordering pinned; default (enforce) mode launches succeed with a fully poisoned environment (the bridge's python3 runs in the scrubbed env); bare mode on a host that denies it still fails closed with exit 2 (TJ-GAP-034).
- **RED proof:** with the pre-fix wrapper restored, 46 of these tests fail — including the function-sweep tests.
- **Host-conditional skips are loud and grep-able** (same philosophy as the existing `HOST-DEGRADED-*` lanes): `HOST-DEGRADED-PIDNS` (bare launch), `HOST-DEGRADED-BWRAP` (bwrap), `HOST-DEGRADED-FSISO` (mapped `--user`), `HOST-DEGRADED-USERNS` (no user namespace). A test that cannot run skips with a reason; it never passes vacuously. Host class on the dev box: bare unshare denied and mapped launches denied (AppArmor `unprivileged_userns` — see `scripts/fs-isolation-probe.py`), `--user` unmapped and bwrap both runnable.

## 7. References

- [docs/threat-model.md](../docs/threat-model.md) — system-wide threat model (layers, actors, residual risk)
- [specs/cli.md](cli.md) — standalone CLI contract, jail backends (§4), graceful degradation
- [specs/interruptor.md](interruptor.md) — S05, the Layer-1 command firewall
- `plugin/test_env_scrub.py` — the regression suite backing §4 and §6
- `scripts/fs-isolation-probe.py` — host-class probe referenced by the skip markers
