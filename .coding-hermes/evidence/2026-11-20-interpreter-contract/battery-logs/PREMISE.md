# TJ-DF-074 premise record — composed-mode battery docker probe

Tick `terminal-jail-dogfood-2026-11-20-15-00-01` (record 2026-11-20c) · repo HEAD `81667b1` (== origin/main; product code tip `e67e07e`)
Row: `TJ-DF-074` (pending, P2). Written because the row's committed evidence carried the finding only truncated.

## Premise

On the ephemeral QA agent the composed-mode battery failed three cells (`tests`, `ci-pass` native,
`chaos-resource` capped) and the row claims all three are ONE test premise, not three defects.

## Why it is one test (evidence — raw logs in this directory)

| cell | log | result |
|---|---|---|
| tests | `tests.log` (sha256 `2a54ab658a69e456…`) | `1 failed, 2041 passed, 16 skipped in 132.39s` |
| ci-pass (native) | `native.log` (`a4234edfd439a6fd…`) | same test, `1 failed, 2041 passed, 16 skipped in 129.80s` |
| chaos-resource (3 GiB cap) | `res.log` (`91bae6c6e1b1d6eb…`) | same test, suite ran to completion, `127.35s` |

`res.log` is what makes this a test-premise failure and not a chaos/cap failure: under the memory cap the
suite still reached its own assertion. 2041 other tests passed in every cell.

## The failure, verbatim

```
        monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/nonexistent-docker.sock")
        reason = self.battery._docker_available()
>       assert reason is not None
E       AssertionError: assert None is not None
tests/test_composed_mode.py:474
```

`_docker_available()` concluded a daemon WAS reachable while pointed at an invented socket path.

## Probe contract

`scripts/composed-mode-battery.py:299-315` runs
`subprocess.run([docker, "info", "--format", "{{.ServerVersion}}"], …)` and then:

- `rc != 0` → returns a reason string (`docker daemon unreachable…`) → the test passes;
- `rc == 0` → returns `None` = "daemon available" → the test fails, **regardless of stdout**.

So the probe rides on exactly one observable: the exit code of whatever `docker` `shutil.which()`
resolves. Empty output is not checked.

## Local red-proof, both arms (this host, repo HEAD `81667b1` / code tip `e67e07e`, no docker installed or invoked)

```
# arm 0 — PATH docker that exits 0
printf '#!/bin/sh\necho "28.5.2"; exit 0\n' > $SHIM0/docker; chmod +x $SHIM0/docker
PATH=$SHIM0:$PATH python3 -m pytest tests/test_composed_mode.py -k unreachable_daemon -x -q
→ 1 failed in 0.04s, identical signature `assert None is not None` @ :474   (red-arm-rc0-shim.txt)

# arm 1 — PATH docker that cannot connect
printf '#!/bin/sh\necho "Cannot connect to the Docker daemon" >&2; exit 1\n' > $SHIM1/docker
PATH=$SHIM1:$PATH python3 -m pytest tests/test_composed_mode.py -k unreachable_daemon -x -q
→ 1 passed in 0.02s                                                        (green-arm-rc1-shim.txt)
```

The test fails **iff** the resolved `docker` exits 0. No socket, daemon or container is needed to
reproduce the agent's failure — any executable named `docker` that exits 0 does it.

## What the agent run itself shows (evidence)

`ci.log` line 1 of the same battery: act used `docker host 'unix:///run/bunker/f884d320/docker.sock'`.
The harness therefore exported `DOCKER_HOST` to the agent's own answering socket, and the docker CLI
on that host **honored** it.

Hence "the agent's docker CLI ignores `DOCKER_HOST`" is ruled out for that host.

## Remaining candidate classes (INFERENCE — not verified; agent `f884d320` was destroyed at teardown)

1. The pytest child resolved a **different** `docker` than act did (harness shell PATH vs `~/tools/venv`
   pytest PATH). A wrapper/shim that exits 0 reproduces arm 0 exactly.
2. The resolved CLI exits 0 on an unreachable socket while printing nothing, and `:315` accepts it because
   stdout is never inspected.

Both live in the same seam: the probe trusts an exit code it does not own, and the test asserts on an
executable resolution it does not control. Requiring a non-empty `ServerVersion` at `:315` closes class 2
mechanically; pinning the probe's executable (absolute path, or PATH isolation inside the test) closes class 1.

## Boundary

Not attributable further without a live agent, and a fresh JIT spawn is the install leg's cost, not this
row's. `bunker-mvp` was refused at admission (disk 95% > 94%) during the 2026-11-20b run; `bunker-las-03`
took `f884d320`. No code was modified and no row status was changed by this record.
