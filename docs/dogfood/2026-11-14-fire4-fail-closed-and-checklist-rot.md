# Fire 4 — fail-closed claims, and the maintainer checklist that cannot pass

Dogfood tick `terminal-jail-dogfood-2026-11-14-10-01-04`, continuation fire 4, 2026-11-14.

No code was modified by this lane. No board row was closed. The install leg was **not**
re-run (it ran earlier this tick: 24-cell terminal battery on bunker-mvp, ledger at
`docs/dogfood/2026-11-14-install-battery-ledger.md`), so no `SKIPPED-install-bunker` row is
owed. Product source is byte-identical to fire 3's re-time pin `8c8097e` — the only files
that moved between `8c8097e` and HEAD `8fb5e4b` are this log, the fire-3 deltas doc, and a
`ch:trace` comment binding in `plugin/test_tjdf047_fs_degrade_plain_allow.py` — so fire 3's
timings still bind and **no `PERF` row** is warranted.

## 1. Fire 3's open boundary (c) — RESOLVED, negative

Fire 3 carried "pipx channel still unverified". Resolved by reading the published channel
and the docs, not by installing:

```
$ curl -sS https://pypi.org/pypi/terminal-jail/json -w 'HTTP=%{http_code}\n'
HTTP=404
```

That is consistent with the project's own statement, README:199 — *"PyPI is not a
distribution channel for this project: there are no terminal-jail packages on PyPI …
always fails by design"* — and with `docs/supply-chain.md:57` and `docs/quickstart.md:50`.
So the pipx channel is **not a defect and not a gap**: it is a documented non-channel, and a
private pip channel that returns `Could not find a version` (already owned by
`QA-TERMINAL-JAIL-11`) is consistent with it rather than hidden behind it.

## 2. Fail-closed claims — all three hold (positive, nothing filed)

A trust-focused tool is only worth what it does when it *cannot* honour a request. Every
refusal below exits **2**, names the cause, and says the command did not run:

```
backend=unshare + --private-proc | rc=2 | TERMINAL_JAIL_PRIVATE_PROC=required but the
  resolved backend 'unshare' cannot provide a <private /proc>
backend=nonsense                | rc=2 | unknown TERMINAL_JAIL_JAIL_BACKEND='nonsense'
  (expected auto, bwrap, or unshare); command not run
backend=unshare (plain)         | rc=2 | namespace creation failed (unshare exit 1);
  command not run — on unprivileged hosts try <hint>
```

`--private-proc` on the resolved bwrap backend really is private: **4** numeric entries in
`/proc` inside the jail versus **881** on the host, and `/proc/1/exe` resolves to `bwrap`
(the jail's own init), not to the host init. No silent downgrade was observed anywhere on
this axis.

## 3. FINDING — `docs/quarterly-review.md` §3 cannot pass on a healthy build → `TJ-DF-067`

The release/quarterly checklist is the file a maintainer runs before declaring a release
verified. Five of its five standalone-CLI checks fail at HEAD on a build that works:

| checklist line | actual |
|---|---|
| `-- echo hello` | rc 127, `terminal-jail: --: command not found` |
| `--user --pid --fork -- echo hello` | rc 127, `--pid: command not found` — and neither `--pid` nor `--fork` exists in `--help` |
| `--seccomp -- echo hello` | rc 1, uncaught `FileNotFoundError` traceback |
| `--help` | OK (accurate) |
| `--version` | OK, prints `1.3.3` |

The wrapper has no end-of-options terminator at all: the first non-flag argument *is* the
command, so `--` is exec'd as a program. Provenance: the file was last edited by `DOC-3`
(commit `1976e17`, 2026-09-28), which repaired one nonexistent test-file line *above* this
section and never executed the CLI block. Nothing guards the file —
`scripts/docs-check.py` checks fenced-block balance plus a pinned argv list in `README.md`
only (`docs-check.py:4`).

## 4. FINDING — `--seccomp` traceback and wrong exit status → `TJ-DF-068`

Same missing binary, only flags varied:

```
(no flags)       rc 127  clean one-line "command not found"
--user           rc 127  clean
--seccomp        rc 1    Traceback … seccomp-loader.py:77 os.execvp(args[0], args)
--user --seccomp rc 1    same traceback
```

`standalone/seccomp-loader.py:76` prints its usage as `seccomp-loader.py [--] <command>`, but
line 69 does `args = sys.argv[1:]` and never consumes a leading `--`. And the `execvp` at
line 77 is unguarded, so a missing command escapes as a Python traceback with Python's
default exit 1 — neither the pass-through status `specs/cli.md:373` describes nor the
reserved pre-flight `2`. A caller that distinguishes "command not found" (127) from "the
jail refused me" (2/126) is told a typo was an internal failure; a human reads a traceback
as a bug in the tool. This is the one place the product's otherwise excellent refusal
discipline (§2 above) breaks.

## 5. Boundaries still open (stated, not papered over)

- **(a) PATH shadow** — `OPS-TJ-001` (pending P2, owner-gated). The login-shell
  `type -a terminal-jail` probe was blocked by the unattended tool-consent gate in fire 3
  and was not retried by another route; PATH order remains inherited-unverified.
- **(b) True page-cache-cold timing** — needs root to drop caches; all numbers are
  warm-state numbers.
- **(d) Shared-checkout hazard** — `main` moved under fire 3 within the hour. Board state and
  main were re-read immediately before this record was written (parity `0 0`, HEAD
  `8fb5e4b`, CI **success** on that exact sha at 10:57:20Z).

## Verdict

**WORKS AS DOCUMENTED, WITH ONE SILENT HOLE (`TJ-DF-066`) — and a maintainer-facing
checklist that no longer describes the tool.** Containment and fail-closed behaviour are
kernel-real and verified again here; the silent rule hole `TJ-DF-066` is unchanged; this
fire adds two doc/error-surface defects (`TJ-DF-067`, `TJ-DF-068`) that a real user hits on
their first typo or their first release check.
