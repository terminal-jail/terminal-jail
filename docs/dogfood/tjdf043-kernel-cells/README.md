# TJ-DF-043 kernel-matrix evidence cells (raw, importable)

Raw orphan-teardown cells captured on the two reachable Debian 13 hosts on
2026-10-02, plus the dev host. Files follow the
`scripts/kernel-matrix-teardown.py --import` v1 schema exactly
(`{"rows": [row, ...]}`); import them with:

```console
$ .venv/bin/python scripts/kernel-matrix-teardown.py --import docs/dogfood/tjdf043-kernel-cells/cell-6.12.107-unshare-postfix.json
```

## Naming

`cell-<kernel>-<backend>-<prefix|postfix>.json`

- `prefix`  = the wrapper as of `HEAD` BEFORE the TJ-DF-043 fix
  (util-linux mapped launch, PDEATHSIG armed before the `-S/-G`
  credential change). The unshare `prefix` cells are deliberately FAIL:
  they are the defect's record, retained as evidence.
- `postfix` = the fixed wrapper (mapped launch ends with the
  `setpriv --pdeathsig=SIGKILL` re-arm tail). All postfix cells PASS.

## Capture conditions

- Deviated from nothing in the harness protocol: pre-launch
  `sleep 300` /proc diff, wrapper SIGKILLed, payload-death poll at 20 ms
  granularity. Cells ran 2–3 repetitions each; every repetition's
  per-rep teardown time is inside the row's `evidence` string.
- The Debian cells ran the REAL wrapper (`standalone/terminal-jail` from
  the repo, copied to the host) with `--user`:
  `TERMINAL_JAIL_FS_ISOLATION=mapped` was confirmed live on both hosts
  (payload uid 65534), i.e. the post-fix unshare cells exercised the
  uid-MAPPED launch — the exact shape that orphaned pre-fix.
- The dev host (Ubuntu 26.04, kernel 7.0.0-31) CANNOT create the mapped
  launch (AppArmor denies setuid/setgroups inside unprivileged user
  namespaces), so its green cells only ever exercised the mapping-less
  shape — recorded as such in docs/backend-parity.md.

## Where each number came from

| File | Kernel | Backend | Verdict | Survival |
|---|---|---|---|---|
| cell-6.12.107-unshare-prefix.json | 6.12.107+deb13-amd64 (bunker-las-03) | unshare (mapped) | FAIL | >5 s, 2/2 reps |
| cell-6.12.107-unshare-postfix.json | 6.12.107+deb13-amd64 (bunker-las-03) | unshare (mapped) | PASS | 20 ms, 3/3 reps |
| cell-6.12.107-bwrap-postfix.json | 6.12.107+deb13-amd64 (bunker-las-03) | bwrap | PASS | 20 ms, 2/2 reps |
| cell-6.12.101-unshare-prefix.json | 6.12.101+deb13-amd64 (bunker-las-02) | unshare (mapped) | FAIL | >5 s, 2/2 reps |
| cell-6.12.101-unshare-postfix.json | 6.12.101+deb13-amd64 (bunker-las-02) | unshare (mapped) | PASS | 20 ms, 3/3 reps |
| cell-6.12.101-bwrap-postfix.json | 6.12.101+deb13-amd64 (bunker-las-02) | bwrap | PASS | 20 ms, 2/2 reps |

Mechanism and citations: `docs/backend-parity.md` known-limit (e).
The matrix (dev host + these two kernels = 3 kernels) is imported and
summarized by the harness; a third kernel's cells must still come from a
real host before any green-matrix claim (the harness never upgrades an
import to an execution).
