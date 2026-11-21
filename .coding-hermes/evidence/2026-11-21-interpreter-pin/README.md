# TJ-DF-073 — evidence: a broken `TERMINAL_JAIL_PYTHON` pin refuses with the wrong box

Worktree `/home/kara/worktrees/terminal-jail-TJ-DF-073` (branch `wt/TJ-DF-073`),
measured 2026-11-21 on the fleet host. Prior measurement: `../2026-11-20-interpreter-contract/`
(unchanged by this work).

## The contract under test

`standalone/terminal-jail` runs the pinned interpreter twice before the tier
launch (JSON-escaping the command, then running the bridge):

    _TJ_BRIDGE_PY=${TERMINAL_JAIL_PYTHON:-python3}          # :293
    ... | "$_TJ_BRIDGE_PY" "$bridge" || return 1            # :347-348

An unusable pin therefore failed at the first exec, bash printed its own raw
`line 347/348:` noise, and control fell into the *bridge-unavailable* handler —
`./install.sh` / `TERMINAL_JAIL_BRIDGE` guidance for a fault that lives in the
pin — while `COMMAND BLOCKED — interpreter-unavailable` (the documented refusal
for an unusable interpreter) was unreachable for the very fault it names.

## Red proof (before), green proof (after)

Probe: `scripts/probe_pins_0721.sh <out-dir> <wrapper-path> [bridge-path]`.
Before-fix arms live in `arms-before/`, after-fix arms in `arms-after/`
(`.rc`, `.out`, `.err` per arm). Every arm is a firewall-ON invocation
(`--interruptor` is the default).

| arm | rc before→after | box before | box after | first stderr before → after |
|---|---|---|---|---|
| a3-pin-missing (missing path) | 126→126 | interruptor-bridge-unavailable | **interpreter-unavailable** | `line 347: /…/nope/python3: No such file or directory` → `+---…` (box) |
| a4-pin-notexec (not executable) | 126→126 | interruptor-bridge-unavailable | **interpreter-unavailable** | `line 348: …/noexec-python: Permission denied` → `+---…` (box) |
| a5-pin-notonpath (bare name off PATH) | 126→126 | interruptor-bridge-unavailable | **interpreter-unavailable** | `line 348: no-such-python-here: command not found` → `+---…` (box) |
| a5b-pin-exec-fails (executable, execution fails) | 126→126 | interruptor-bridge-unavailable | **interpreter-unavailable** | `+---…` (box) → `+---…` (box) |
| a6-warn-broken-pin (warn mode) | 0→0 | — (fail-open) | — (fail-open) | `line 347: … Permission denied` → `terminal-jail: WARNING — interruptor bridge not available; running without firewall (warn mode)` |

Raw bash exec noise, grep `\bline [0-9]+:`:
`arms-before/` **4 arms, 8 noise lines**; `arms-after/` **0**.

The after box names the pin and the cause, and says nothing about install.sh:

    |  TERMINAL_JAIL_PYTHON=/mnt/ssd/tmp/tj-df-073/nope/python3 (no such file)
    |  Refused before the command-firewall evaluation; the command did not run.

Enforce arms keep `rc=126`, `stdout` empty, payload never runs (`a3`–`a5b`
`stderr` carry no `PIN-ARM-RAN`). Warn mode (`a6`) still runs
(`WARN-PAYLOAD-RAN`, rc 0) and still states the degradation.

Controls (firewall alive on this host, measured in both runs):

| arm | rc | stdout |
|---|---|---|
| a2-allow-baseline | 0 | `ALLOW-PAYLOAD-RAN` + `verdict action=allow` on stderr |
| a7-pin-good (`TERMINAL_JAIL_PYTHON=/usr/bin/python3`) | 0 | `PINNED-PAYLOAD-RAN` + `action=allow` |
| a8-pin-empty (`TERMINAL_JAIL_PYTHON=`) | 0 | `EMPTY-PIN-PAYLOAD-RAN` + `action=allow` |
| a9-block-control (`rm -rf /`) | 126 | empty; `action=block`, `rule_id=builtin-rm-rf-root` |

Every fault class the row names is reproducible on this host (a3, a4, a5); the
extended class a5b (a pin that resolves and is executable but whose execution
fails) is also reproducible and is now refused the same way.

## Fix shape (see the wrapper's TJ-DF-073 comments)

1. `_tj_pin_preflight` — called immediately before the first bridge exec; a
   static fault (`(no such file)` / `(not executable)` / `(not on PATH)`) is
   refused with the interpreter box in enforce mode, and warn mode is untouched.
2. `_interruptor_evaluate` returns "unavailable" instead of EXEC'ing a pin it
   knows cannot run — this is what removes bash's raw exec noise.
3. The bridge-unavailable enforce branch asks `_tj_interpreter_fault_deep`
   (static classes, then a one-shot `<pin> -c pass` probe) and refuses with the
   interpreter box when the pin is the cause — covering the exec-fails class
   without paying a probe on healthy invocations.
4. `_tj_interpreter_unavailable_box` is now the ONE box for both arrival paths
   (pre-bridge and pre-tier-launch); its middle sentence no longer claims the
   seccomp/Landlock loader specifically, since the same box also refuses before
   the firewall evaluation.

## Tests

Red proof (wrapper + both copies restored to `HEAD` before the fix, new tests
kept): `tests/redproof-prefix-standalone-missing.txt` — 13 failed, 15 passed,
with the production failure quoted verbatim (`line 348`/`line 347` noise, then
`interruptor-bridge-unavailable`).

    .venv/bin/python -m pytest plugin/test_wrapper_landlock_interpreter.py -q
        -> 28 passed   (4 fault classes x both copies, source-order gate, warn arm)
    .venv/bin/python -m pytest plugin/test_wrapper_landlock_interpreter.py tests/ -q \
        -k "interpreter or refusal or bridge"
        -> 30 passed, 170 deselected
    .venv/bin/python -m pytest tests/ -q
        -> 169 passed, 3 skipped
    .venv/bin/python -m pytest plugin/ -q
        -> 2012 passed, 12 skipped
    .venv/bin/ruff check .        -> All checks passed
    shellcheck -S warning standalone/terminal-jail -> clean
    cmp -s standalone/terminal-jail plugin/terminal_jail/_bundled/terminal-jail -> 0

`plugin/test_packaging_wheel.py::TestUnactivatedVenvBridgeInterpreter::test_explicit_missing_interpreter_fails_loudly_without_fallback`
was pinning the OLD box for this exact fault; it now asserts the corrected
contract (`interpreter-unavailable`, no `install.sh`, no `line N:` noise) with
the fail-loud intent unchanged (rc 126, payload never ran).

## Note on the bundled copy

The probe is run against `standalone/terminal-jail`. `plugin/terminal_jail/_bundled/terminal-jail`
is a data file that only resolves its bridge inside an install layout (the
wrapper strips `PYTHONPATH` by design, TJ-DF-043 era hygiene), so running the
probe on the bare bundled file reports `[bridge-error] interruptor engine not
importable` for EVERY arm including the controls — a layout artifact, not
evidence. The bundled copy is therefore proved by (a) `cmp` byte-identity with
the measured file and (b) the pytest arms above, whose `wrapper` fixture stages
a wheel-shaped install layout and parametrizes over BOTH copies.
