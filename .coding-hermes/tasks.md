
## Dogfood Findings (2026-09-15)
Verdict: PROMISING-BUT-ROUGH (roughness moved: docs/firewall/install now deliver; the `--user` isolation claim doesn't)
Promise: A user can contain terminal commands (PID namespace, firewall, privilege drop, seccomp) via the standalone CLI `terminal-jail`, with `--user` fallback on hosts denying unprivileged PID namespaces.
Time-to-first-success: <1 min local; bunker fresh-machine clone→install→smoke <2 min (install 0s, smoke ok, probe DEGRADED as documented).

- [P0] TJ-DF-015 — `--user` "nobody" is an unmapped-namespace illusion: NO filesystem isolation. `unshare --user` launches with no uid mapping; uid displays show 65534 but DAC evaluates as the caller (owner). Verified: jailed process read a mode-600 caller file and created files in caller HOME as kara:kara; control `sudo -u nobody` → errno 13. Also baked into engine auto-sandbox prefix. Fix: real uid mapping (--map-auto / newuidmap+subuid); interim: document `--user` = PID containment + env scrub only. Evidence: docs/dogfood/2026-09-15-integration.md §4.
- [P1] TJ-DF-016 — warn mode on EPERM hosts dies silent: preflight exit 2 precedes the WARN line, so "warn = warns, allows" never materializes end-to-end on DEGRADED hosts. Fix: evaluate firewall before preflight, print verdict regardless of namespace outcome.
- [P2] TJ-DF-017 — quickstart/skill verify example (`--user echo "in jail"`) proves no containment property on EPERM hosts; pidns-capability-probe.py still not wired into the verify block. Fix: probe first, branch FULL/DEGRADED.
- [P3] TJ-DF-018 — upstream skill drift (NOT this repo): bunker recipe says :19090 but deployed bunkerd listens :10001/:10002; token capture includes YAML quotes. Recorded for the dogfood-skill owner; do not dispatch a foreman on this row.

Prior-run verification (all PASS this run): TJ-DF-011 chmod variants block at bridge AND CLI; TJ-DF-012 same-ID warn override warns on stderr; TJ-DF-014 env scrub live; DF-TERMINAL-JAIL-3 reinstall backs up edited rules. Install leg: local scratch-HOME + ephemeral bunker (las-bunker-03) both clean; no SKIPPED-install-bunker.

Verdict: PROMISING-BUT-ROUGH
Promise: {"entry_point":"Standalone CLI wrapper: standalone/terminal-jail (56-line bash script wrapping `unshare --pid --fork --mount-proc --kill-child=SIGKILL bash -c 'exec "$@"'`); plus a JSON bridge firewall API (plugin/terminal_jail/interruptor_bridge.py, reads one JSON command on stdin, returns allow/

- [P1] Firewall bridge fail-open on malformed input is undocumented — Invalid JSON / empty stdin on the interruptor bridge returns action=allow (fail-open) — security-relevant default for a command firewall, documented only in bridge source, absent from README/quickstar
- [P1] Quickstart verify block fails out of the box on this host — 2nd verify command (bare `terminal-jail echo "in jail"`) exits 2 on this EPERM host; the --user fallback is buried in a blockquote and scripts/pidns-capability-probe.py exists but is never surfaced. A
- [P1] Re-running install.sh clobbers customized user rules — install.sh unconditionally overwrites ~/.config/terminal-jail/rules.d/00-builtins.yaml — user rule edits lost on reinstall with no backup or prompt. Also hardcodes $HOME/.local/bin into the PATH-appen
- [P2] Stale rule_id in quickstart bridge example (promise broken) — README/quickstart shows output rule_id "I-BLOCK-001" but the engine emits "builtin-rm-rf-root" — grep target doesn't exist, so doc-driven validation of the firewall fails. One of two explicitly broken
- [P2] warn mode wording misleading on EPERM hosts; --user PATH inheritance undocumented — "warn mode warns, allows" is false on EPERM hosts: firewall passes the command but the namespace layer still exits 2 unless --user is also added. --user jail scrubs USER/LOGNAME/HOME but inherits call
