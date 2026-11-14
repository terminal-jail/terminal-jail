# terminal-jail dogfood — 2026-11-14 fire 5: the auto-sandbox path is dead on a 0700 home, and it does not say so

- **Tick:** `terminal-jail-dogfood-2026-11-14-10-01-04` (continuation fire 5 of this tick; fires 1–4 recorded in
  `.coding-hermes/dogfood-log.md` as 2026-11-14a…d)
- **Target:** `/home/kara/terminal-jail` @ `8aad6df` (`= origin/main`, parity `0 0` at fire start)
- **Binaries under test:** checkout `standalone/terminal-jail` (HEAD build) and installed `~/.local/bin/terminal-jail`
  `1.3.3`
- **Host:** kernel `7.0.0-38-generic`, 16 cores, load ~21 during the probes (numbers below are wall-clock medians of
  30 runs, so they survive that load)
- **Verdict:** **WORKS AS DOCUMENTED ON THE ALLOW PATH. THE AUTO-SANDBOX (MODIFY) PATH IS BROKEN ON THIS HOST AND
  FAILS WITHOUT NAMING ITS CAUSE.** One row filed for the defect (`TJ-REVIEW-074-R2`), one row filed for the skipped
  install leg (`TJ-DF-069`).
- **Constraint honoured:** this lane changed no code, closed no row, touched no repo visibility or permission, minted no
  credential. Every probe ran in `/home/kara/.hermes/cache/scratch/tj-dogfood-20261114/fire5/` against the product as a
  user drives it.

---

## 1. What a user actually does, and what happens

The product's promise on the front page is: *your terminal commands run inside a jail; dangerous ones are blocked,
builds are modified to run sandboxed.* So the real-use script is a build, not `--version`:

```bash
mkdir -p /tmp/build && cd /tmp/build && printf 'ok:\n\t@echo PAYLOAD-RAN\n' > Makefile
terminal-jail make ok
```

Observed (clean env — all nine `TERMINAL_JAIL_*` variables unset — cwd outside the checkout, defaults on):

```
rc=126
stdout: (empty)
stderr: {"event":"verdict","action":"modify","rule_id":"auto-make","reason":"Command modified by auto-sandbox"}
        [terminal-jail] Modified: make ok
        bash: line 1: /home/kara/.hermes/hermes-agent/venv/bin/python3: Permission denied
```

The user asked for a build, got a firewall verdict that reads like a success ("Command modified by auto-sandbox"), and
then a `Permission denied` from **bash** about a **python3** they never mentioned. `PAYLOAD-RAN` never appears. Nothing
on any surface says the command did not run, or why.

## 2. Isolating the cause (2×2×3 matrix, all read-only)

| # | binary | backend/tier | cwd | result |
|---|--------|--------------|-----|--------|
| A | checkout @ `8aad6df` | tier **ON** (default) | outside checkout | **rc=126**, `Permission denied` on the venv python3 |
| B | checkout @ `8aad6df` | `TERMINAL_JAIL_LANDLOCK=0` | outside checkout | **rc=0**, `PAYLOAD-RAN` |
| C | checkout @ `8aad6df` | tier ON + `TERMINAL_JAIL_PYTHON=/usr/bin/python3` | outside checkout | **rc=126**, *same venv path* in the error — the pin is ignored |
| D | checkout @ `8aad6df` | `TERMINAL_JAIL_SANDBOX=off` | outside checkout | rc=0 (sandboxing removed, tier irrelevant) |
| E | installed `1.3.3` | defaults | same cwd | **rc=0**, `PAYLOAD-RAN` — because its loader is unreadable, so the tier silently degrades |
| F | checkout @ `8aad6df` | tier ON, cwd **inside** checkout | inside | rc=126 — cwd is not the variable |

Host facts that close the loop:

- `/home/kara` is `drwxr-x--x` (traversable by other uids), but **`/home/kara/.hermes` is `0700`** — and the interpreter
  the rewrite splices in, `python3`, resolves on this host to
  `/home/kara/.hermes/hermes-agent/venv/bin/python3`, i.e. *inside* that 0700 directory.
- `/usr/bin/python3` is `root:root` and readable, which is why cell C *should* have worked and does not.

So the switch is the **existence of the filesystem tier** (A vs B), not the cwd (A vs F), not the binary (A vs E), and
not the sandbox launch itself (D). The tier is doing its job — it denies a path the payload uid cannot traverse. The
defect is that the rewrite resolves and splices an interpreter that the tier will then refuse, and the refusal is
reported by `bash` as a bare `Permission denied` with `rc=126` instead of by terminal-jail as a named verdict.

## 3. Why the guard that exists does not catch this

`standalone/terminal-jail` in this very tree carries the named-cause machinery that `TJ-REVIEW-074` was closed on:

- the rewrite's interpreter preflight and its named verdict — `standalone/terminal-jail:1267`, with siblings at
  `:1280` and `:1294`;
- the filesystem-tier branch that installs the Landlock domain — `standalone/terminal-jail:1449-1487`.

The ordering is the bug: the preflight asks *"does this interpreter resolve and execute in the namespace?"* **before**
the Landlock domain is installed, so a tier denial of an otherwise-executable interpreter is invisible to it. The
regression test that pins the promise, `plugin/test_modify_preflight.py:291`
(`test_modify_rewrite_interpreter_denial_is_named`), stubs `unshare` and denies via a mode-`0644` shebang target — i.e.
it exercises exactly the pre-tier shape the preflight *can* see. A tier-installed denial is a different ordering and has
no test.

That is the honest finding: **not "the fix was reverted", but "the fix covers one shape of the failure and the other
shape is the one this host produces"** — the same pattern the diagnostics trail already records twice (§9.1 "a fixed
rule class that only covers the shape it was built for").

## 4. What still works (so the report is not a single string of failures)

Using the product as a user for an hour produced mostly working surfaces:

- the **allow path** is solid: four-for-four documented verdicts (`echo`→`allow/allow-echo`, `date`→`allow/null`,
  `rm -rf /`→`block/builtin-rm-rf-root`, `make test`→`modify/auto-make`), and `--version` / capability probes return
  in tens of milliseconds;
- **containment is real**: a canary file readable from the host is denied inside the jail by default and readable under
  `TERMINAL_JAIL_LANDLOCK=0` — the tier is not decorative;
- **fail-closed refusals hold** (re-verified, nothing filed): unknown backend, `--private-proc` on a backend that cannot
  provide it, and schema-broken rule files all refuse with a readable sentence naming the field and the file;
- the **structured audit trail is well-formed**: one JSON event per decision, parseable, with the matched rule id.

The one thing that does *not* work is the headline "builds run sandboxed" path on any host whose `PATH` puts a
project's `python3` under a `0700` home — which is most developer machines, including this one.

## 5. Performance (Step 2b): nothing here is slow enough to file

The headline operation timed warm and cold (30 runs, median, clean env, this loaded host):

| operation | warm | cold (page-cache dropped between runs) |
|---|---|---|
| bare `/bin/true` floor | ~3 ms | ~4 ms |
| `terminal-jail /bin/true` | ~250 ms | ~265 ms |
| `terminal-jail --version` | 35 ms | 38 ms |
| the modify-path wrapper's start-up import | 35 ms | 38 ms |

- The wrapper costs **~250 ms** per allow-path invocation and the tier attach accounts for **+67 ms** of it — the same
  order already recorded against `TJ-DF-048` (+120 ms, 2026-10-17) and §23.6 (+67 ms, 2026-11-14). No regression.
- **Cold vs warm shows no measurable penalty** (35 vs 38 ms), so there is no page-cache cliff to chase.
- No profile is justified by these numbers, so none was taken: a user does not feel 250 ms on a build command, and the
  one path that *is* unusable (A above) fails in ~0 ms rather than being slow.

**Therefore: no `PERF-<n>` row is filed this fire.** Stating it plainly, as the tick requires: nothing on this product
is slow enough that a user would notice, and filing a win nobody can feel would devalue the real rows.

## 6. Install leg — SKIPPED, and filed as such

The fresh-machine leg did **not** run this fire, and is not claimed.

- Driver present: `/home/kara/.hermes/scripts/bunker-qa.sh` exists.
- Host absent: `curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://bunker-mvp:8765/health` → **000**
  (captured at fire start in `bunker_now.txt`).
- The install proof on file does **not** cover the tree under test: the battery recorded in
  `2026-11-14-install-battery-ledger.md` ran at `489bbd4`, but `git diff --stat 489bbd4..8aad6df` shows the product
  itself moved afterwards — `88cf92f`/`a48809c` rewrote the bwrap fs-tier branch of both `standalone/terminal-jail` and
  `plugin/terminal_jail/_bundled/terminal-jail` (53 lines each).

Filed as `TJ-DF-069` (`[dogfood:P2] SKIPPED-install-bunker`), following the precedent of `TJ-DF-036` and
`DF-TERMINAL-JAIL-14/19/26`. A silent pass would have been a lie: the product changed after the battery.

## 7. Diagnostics trail (this fire, in order)

| step | probe | what it settled |
|---|---|---|
| 1 | `repo_state.txt`, `repo_delta.txt` | HEAD `8aad6df` = `origin/main`, parity `0 0`; one pre-existing uncommitted board hunk (`@@ -372 +372 @@`) and a sibling's dirty `plugin/test_tjdf047_fs_degrade_plain_allow.py` — **not written by this lane** |
| 2 | `probe2.log`, `probe3.log` | inside the jail `HOME`/`PWD`/`.git` visibility and uid mapping; the payload runs as the caller, so host modes are what decide access |
| 3 | `probe4.log`, `probe9.log` | `auto-make` fails the same way regardless of cwd or interpreter on `PATH` → not a cwd bug |
| 4 | `probe5.log`, `probe8.log` | status matrix 0/1/3/7/42/255 through the wrapper: allow path translates statuses correctly; the modify path is where `126` appears and the loader (`standalone/landlock-loader.py:91`, `os.execvp`) does no translation of its own |
| 5 | `probe7.log` | driving the repo bridge directly shows the rewrite string: `unshare --user --pid --fork --kill-child=SIGKILL bash -c "python3 <landlock-loader.py> -- <cmd>"` — the bare `python3` is the splice |
| 6 | `probe10.log` + `docs_read_claims.txt` | read-visibility matrix for the user's own tree against the documented claims — the docs do not promise the tier grants an interpreter path |
| 7 | `probe11.sh`, `matrix.sh` | the 2×2×3 matrix in §2 above: tier ON is the switch, `TERMINAL_JAIL_PYTHON` is ignored |
| 8 | `perf.sh`, `ab.sh` | warm/cold timings and installed-vs-checkout A/B (§5) |
| 9 | `probe12.log` | the full stderr audit trail of a modify-path launch: **exactly one** JSON event (the verdict), zero outcome/exit-status events, plus two non-JSON lines — the trail cannot distinguish "sandboxed and ran" from "never ran" |
| 10 | `bunker_now.txt` | install-leg reachability (`000`) — the SKIPPED row's evidence |

Evidence lives in `/home/kara/.hermes/cache/scratch/tj-dogfood-20261114/fire5/` (probe scripts + logs, `perf.log`,
`ab.log`, `matrix.log`, `repo_state.txt`, `repo_delta.txt`, `docs_read_claims.txt`, `board_dedupe.txt`,
`changelog_dogfoodlog.txt`, `conv.txt`, `bunker_now.txt`, `audit_spec.txt`, `rows.txt`, `facts.txt`, `prod_diff.txt`).

## 8. Rows filed

| id | priority | what |
|---|---|---|
| `TJ-REVIEW-074-R2` | P2 | recurrence of `TJ-REVIEW-074`'s promise: the modify-path interpreter preflight runs **before** the fs tier, so a tier-denied `python3` passes it and the payload dies with a bare `bash: Permission denied`, `rc=126`, no named verdict |
| `TJ-DF-069` | P2 | `SKIPPED-install-bunker` — bunkerd unreachable (`000`), and the on-file install proof (`489bbd4`) predates product changes at `88cf92f`/`a48809c` |

Related rows left alone (already owned): `RELEASE-TJ-021` (pending — trampolines hardcode `python3`, ignore
`TERMINAL_JAIL_PYTHON`; cell C is live evidence), `TJ-DF-048` (tier overhead), `TJ-DF-050` (closed — same class, net
loader), `QA-TERMINAL-JAIL-32` (install test).

## 9. What a user should do today (until the fix lands)

```bash
# the build path with the fs tier off — containment lost, build works:
TERMINAL_JAIL_LANDLOCK=0 terminal-jail make
# or keep the tier and put a readable interpreter first on PATH:
TERMINAL_JAIL_PYTHON=/usr/bin/python3 ...   # does NOT work yet — see RELEASE-TJ-021
```

The workaround that actually works is the first one; the second is the fix's target, not a current escape hatch. That
asymmetry — the only working workaround is "turn the security feature off" — is the reason this row is P2 rather than
P3.
