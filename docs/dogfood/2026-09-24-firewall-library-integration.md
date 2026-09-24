# Dogfood Integration — 2026-09-24 — Firewall-as-a-Library (JSON bridge) + uninstall leg

**Angle (9th run):** runs 1–8 covered the CLI, auto-sandbox, rule packs, the plugin in the
live gateway, and seccomp. This run used the surfaces they never touched: the interruptor
as a **Python library consumed from a scratch project** via its documented firewall API
(the `interruptor_bridge.py` JSON protocol, "safe to script" per docs/dogfood/2026-08-10),
and the **documented `--uninstall` path** on a fresh machine.

## Promise under test

"a user can script the firewall: feed one JSON line
`{"command": ...}` to `plugin/terminal_jail/interruptor_bridge.py`, get one JSON verdict
`{action, command, modified, rule_id, reason}` back — and a fresh user can install, verify,
and cleanly uninstall terminal-jail from scratch following the docs."

## What I did

- Wrote a real consumer program (`/tmp/dogfood-tj-20260924/consumer.py`, outside the repo)
  that drives the bridge as a subprocess, asserts the documented verdict contract on the
  happy paths (allow / block / modify / default-allow), and probes the edges a careful
  integrator worries about.
- Fresh-machine leg on an ephemeral bunker-las-03 agent (6776a2da, destroyed after use):
  clone from the public GitHub URL, documented install, documented smoke, then the
  documented `--uninstall` with a user-authored rule staged to test the preserve promise.

## What held up (contract is genuinely good)

- Happy paths: allow names its rule (`allow-ls`), block names its rule
  (`builtin-rm-rf-root`), modify carries the rewritten command + rule (`auto-make`), and
  default-allow is honestly marked with `rule_id: null` — a script CAN tell an approval
  from a pass-through. This was DF-12's complaint in the 09-17 run; as a library
  consumer I confirm it is fixed.
- Transport failures are structured fail-open with a `[bridge-error]` reason and rc=0:
  invalid JSON, empty stdin, non-dict payload, missing/non-string `command`. No
  tracebacks, no garbage on stdout. A integrator can machine-read every failure.
- Engine-evaluation failures fail CLOSED (`[bridge-error]` → block; TJ-GAP-070).
- Fresh install on a bare Debian user: clone 5s, `./install.sh` <1s, smoke PASS
  (v1.2.0, host FULL, jail PID-ns inode differs from host, blocked test rc=126).
- **Uninstall leg (first real use ever): PASS on every documented promise** — wrapper,
  lib tree, `00-builtins.yaml`, and the rc-file PATH block removed; the user-authored
  `99-mine.yaml` was preserved and listed as `left in place (user-authored)`; second
  `--uninstall` run was an idempotent no-op rc=0.

## Finding 1 — long commands hang the engine (P1)

One 8KB argument costs **7.5s of pure CPU** inside the bridge; 20KB+ never returns
(timed out at 10s in a bisect). The blowup is superlinear in argument length:

| arg length | bridge wall time |
|---|---|
| 500 B | 0.11s |
| 2,000 B | 0.65s |
| 8,000 B | 9.22s (7.5s engine + startup; intercept() alone = 7.491s) |
| 20,000 B | >10s (gave up) |

cProfile names the hot path precisely: `matcher.py:115 _match_pattern` — 145
`re.Pattern.search` calls, **7.555s of 7.566s (99.8%) of self-time**. The rule regexes
backtrack catastrophically on long arguments. The parser is innocent (0.004s).

Why it matters beyond speed: the deployed shim evaluates EVERY shell invocation through
this bridge before exec. Any agent command that happens to carry a multi-KB argument
(a base64 blob, a heredoc captured in a variable, a long prompt echo) freezes the shell
for seconds to forever — a latency self-DoS reachable without any security rule firing.
Cheapest mitigations for the maintainer: a length guard (commands over N KB skip
regex matching and emit a conservative verdict), or per-rule timeouts
(`regex` module / RE2-style engines), or pre-compiling rules with possessive
quantifiers/atomic groups where the patterns allow it.

Reproduce:
```bash
python3 - <<'EOF'
import json, subprocess, sys, time
cmd = "echo " + "a" * 8000
t = time.time()
subprocess.run([sys.executable, "plugin/terminal_jail/interruptor_bridge.py"],
               input=json.dumps({"command": cmd}), capture_output=True, text=True, timeout=30)
print(f"{time.time()-t:.2f}s")
EOF
```

## Finding 2 — `--list-rule-packs` exits 2 on a fresh host (P2)

On a bare machine without PyYAML, the purely informational `./install.sh --list-rule-packs`
prints the pack list AND then refuses with `rule-pack-tool: refused: shipped pack ...
cannot be read (PyYAML is not installed...)`, exiting 2. This differs from the plain
install's documented and correct behavior (pack install is a **skip, not a failure**,
rc=0). Consequence: any docs/bootstrap script that chains
`./install.sh --list-rule-packs && ./install.sh` aborts before installing anything —
that is exactly how the first install attempt on the bunker produced zero files while
looking like a run. An informational listing that cannot list what it cannot parse
should print `db: unreadable (PyYAML missing)` and exit 0.

## Finding 3 — docs gap: the JSON bridge is undocumented in quickstart (P2)

The bridge protocol lives only in a 2026-08-10 dogfood report and the module docstring.
Nothing in docs/quickstart.md, README, or docs/ tells a library consumer the one JSON
line in / one JSON line out contract, the field semantics (when is `rule_id` null),
or the fail-open vs fail-closed split (TJ-GAP-070). I had to read
`interruptor_bridge.py` source to confirm the contract before relying on it — the
skill counts "had to read source to proceed" as a finding. Suggested fix: a short
"Scripting the firewall" section in docs/quickstart.md §3b.

## Verdict on the library angle

The firewall API is **trustworthy as a script surface** (structured verdicts, honest
default-allow provenance, fail-closed engine path) but **not yet safe to put in front of
arbitrary command lengths**. P1 fix is small and targeted at matcher.py:115.

## Consumer snippet that worked (the integration pattern)

```python
import json, subprocess, sys

def verdict(cmd: str) -> dict:
    p = subprocess.run(
        [sys.executable, "/path/to/terminal-jail/plugin/terminal_jail/interruptor_bridge.py"],
        input=json.dumps({"command": cmd}), capture_output=True, text=True, timeout=10,
    )
    return json.loads(p.stdout.splitlines()[-1])

v = verdict("ls -la")
assert v["action"] == "allow" and v["rule_id"] == "allow-ls"
v = verdict("rm -rf /")
assert v["action"] == "block" and v["rule_id"] == "builtin-rm-rf-root"
v = verdict("make test")
assert v["action"] == "modify" and v["modified"].startswith("unshare --user")
```
