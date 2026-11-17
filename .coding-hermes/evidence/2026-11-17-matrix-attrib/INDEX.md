# Matrix-attribution delta — the leg the earlier fires of this tick left UNVERIFIED

Tick: `terminal-jail-dogfood-2026-11-17-11-52-37` (third dispatch of the same tick; records-only re-fire).
Target: terminal-jail, authoritative tip **origin/main `f00967d`** (`test_install.py:295` carries the
unconditional `(test_bin / "unzip").unlink()`).
Measurement window: 2026-11-17 08:00–08:35 local, host 16 cores, loadavg **28.2 → 29.5** (1-min) during
the runs. Pass/fail counts are load-independent; **durations are not** and are quoted only for scale.

## What was unverified and why this settles it

The first two fires of this tick recorded, verbatim:

> the Python 3.11/3.12/3.13 matrix jobs each failed at "Run tests" (7m50s / 8m9s / 8m6s) which is
> consistent with the same unzip premise but was NOT individually re-attributed, so it is recorded as
> unverified for those three jobs

Those job logs were never harvested and the battery agent (`db56b071`) was destroyed, so the logs are
unrecoverable. The leg can therefore only be closed **by mechanism**, not by log: reproduce the exact CI
step on all three matrix interpreters with `unzip` visibility as the ONLY variable, and measure what
changes.

## Method

- Command = the workflow's own step (`.github/workflows/ci.yml:38`), verbatim minus the coverage flags
  (coverage instrumentation changes no outcome and needs `pytest-cov` in the arm venv):
  `pytest plugin/ tests/ -v --tb=short -m "not integration"`
- Tree = `git archive origin/main | tar -x` (immutable copy; the live checkout is shared with sibling
  foreman lanes and was never written).
- Arm A PATH = a directory of **2883 symlinks** to every tool in `/usr/local/bin /usr/bin /bin /usr/sbin
  /sbin` **except `unzip` and `zipinfo`**; Arm B PATH = `/usr/local/bin:/usr/bin:/bin` (host `unzip` at
  `/usr/bin/unzip`). Nothing else differs — same tree, same venv, same command, same window.
- Interpreters = the three the matrix names: CPython 3.11.15, 3.12.16, 3.13.13; pytest 9.2.0 in each
  throwaway venv (`setup_venvs.sh`).
- Arm C = one **real `git clone --no-hardlinks`** at `f00967d`, unzip present, same command with `-q`:
  the green control that separates rig artifacts from product results.

## Results

| ver | arm | unzip | result |
|-----|-----|-------|--------|
| 3.11 | A | no  | **5 failed**, 2076 passed, 12 skipped, 72 deselected — 262.08 s |
| 3.11 | B | yes | 4 failed, **2077 passed** — 218.76 s |
| 3.12 | A | no  | **5 failed**, 2076 passed — 186.46 s |
| 3.12 | B | yes | 4 failed, **2077 passed** — 232.74 s |
| 3.13 | A | no  | **5 failed**, 2076 passed — 201.01 s |
| 3.13 | B | yes | 4 failed, **2077 passed** — 186.57 s |
| 3.11 | C (real clone, unzip) | yes | **0 failed**, 2081 passed, 12 skipped — 185.39 s |

`A − B` is **exactly one test, identically on all three interpreters**:

```
plugin/test_install.py::test_release_wheel_install_without_unzip_uses_python_zipfile
```

`B − A` is empty. The other four failures appear in BOTH arms and are the archive rig, not the product:
each traceback is `fatal: not a git repository (or any of the parent directories): .git`
(`test_tracked_tree_ships_no_vendored_bubblewrap` runs `git ls-files`; the three
`tests/test_release_workflow.py` cases `git clone`/`git tag` the tree). **In a real clone they all pass
— arm C is 0 failed / 2081 passed.**

## What this licenses and what it does not

- **Licensed:** the failure is deterministic, interpreter-independent across the whole matrix, and caused
  by `unzip` being absent from PATH and nothing else. The test unlinks a `testbin/unzip` symlink that
  `_link_tools` (`plugin/test_install.py:80`) only creates when `shutil.which("unzip")` finds one, so on
  an unzip-less box the unlink raises `FileNotFoundError`; on any box with `unzip` the suite is green.
  Any matrix job whose container lacks `unzip` therefore reds at `Run tests` with this single failure —
  which is exactly TJ-DF-071 (still `pending`, P2).
- **NOT licensed:** that the three act job logs *contained only* that failure. The act legs' logs were
  never harvested, the agent is destroyed, and no `catthehacker` image is present locally to re-probe, so
  per-job log attribution stays **UNVERIFIED**; what is proven is the mechanism, on the matrix's own three
  interpreter versions, under the workflow's own command.

## Second boundary of the earlier report (unchanged)

"True page-cache-cold timing still needs root" — confirmed as a policy boundary, not re-attempted:
this lane runs as uid **1000**, `/proc/sys/vm/drop_caches` is `-rw------- root root` → not writable. No
timing was re-run in this fire (loadavg 28+ is not a timing window); the earlier fire's 250–290 ms
first-run series stands as the closest measured arm.

## Files

| file | what it is |
|------|------------|
| `arm-summary.txt` | the table above, every arm's `FAILED` lines, the three A−B deltas, the unzip traceback, arm C |
| `arm{A,B}-{3.11,3.12,3.13}.log.gz` | full verbose pytest output per arm (gzip; `zcat` to read) |
| `armC-clone-green.log.gz` | full output of the real-clone green control |
| `ab_matrix2.sh` | the arm driver (parameterised interpreter; builds the no-unzip PATH) |
| `run_all_arms.sh` | runs 3.11 → 3.12 → 3.13 sequentially |
| `setup_venvs.sh` | builds the three throwaway venvs from the uv-managed CPythons |
| `armC_clone_green.sh` | the clone control |
| `build_evidence.py` | regenerates `arm-summary.txt` from the raw logs (numbers in this file are its output, not typed) |

## Reproduce

```
BASE=/home/kara/.hermes/cache/scratch/tj-1117f
git -C /home/kara/terminal-jail archive origin/main | tar -x -C $BASE/tip
bash $BASE/setup_venvs.sh          # venv311 / venv312 / venv313
bash $BASE/run_all_arms.sh         # 6 arms, ~25 min at loadavg 29
bash $BASE/armC_clone_green.sh     # green control
python3 $BASE/build_evidence.py    # regenerate the summary
```

No product source, board row, visibility or permission was changed by this measurement.

## Disclosure — formatter pass on the evidence script

`build_evidence.py` as committed is **not byte-identical** to the copy that first produced the numbers:
the repo's pre-commit guard refused the first commit (`lint — 1 file would be reformatted`, plus
E401/F401/E741 on the first draft), so the script was rewritten to be lint-clean and then
`ruff format`-ed. The pass is mechanical and was proved so, not asserted: the reformatted script was
re-run over the same raw logs and its output `diff`-ed against the pre-format `arm-summary.txt`
(**identical**), and each regenerated `arm{A,B}-*.log.gz` payload `cmp`-ed against the pre-format
decompressed log (**identical**). Every number in this file therefore still comes from
`build_evidence.py`'s own output over the untouched raw logs.

