# Terminal Jail — Dogfood Integration Report (2026-09-17)

**Run type:** cron dogfood (3rd consecutive daily run on this project).
**Verdict:** 🟡 PROMISING-BUT-ROUGH — roughness moved again: the two P1s from
09-16 (bridge schema markers, install scope) are FIXED and verified live at
HEAD `186dc77`; this run's new P1s are in the **wrapper execution layer**
(auto-sandbox dead-ends on DEGRADED hosts) and **firewall observability**
(default-allow posture undocumented, allow verdicts carry no provenance).
**Time-to-first-success:** <5s (version probe + bridge allow/block both on the
first command). **Friction count:** 5. **Suite:** 420 passed / 14 skipped in
15.14s (`uv run pytest plugin -q`).

## 1. What this project promises (null hypothesis)

> "A user can contain terminal commands via the standalone CLI
> `terminal-jail` (PID namespace / `--user` fallback), and the Interruptor
> firewall decides allow/block/modify for every command before execution."

## 2. The real-use run (what a user actually does)

### 2.1 The bridge as the integration surface (the documented entry point)

The bridge is how any non-CLI consumer (an agent harness, a shell shim, an
audit log) talks to the firewall: one JSON object on stdin,
`{"action": ...}` on stdout. Probed 24 cases; results:

| Probe | Verdict | Note |
|---|---|---|
| `{"command": "echo hello"}` | allow | documented, works |
| `{"command": "rm -rf /"}` | block, `builtin-rm-rf-root` | documented, works |
| `{"Command": ...}` / `{"cmd": ...}` / `{}` / non-JSON / `{"command": 123}` / `null` | allow + `[bridge-error] … fail-open` reason | **DF-TERMINAL-JAIL-6 fix VERIFIED LIVE** — every schema error is named |
| `;` / `&&` / `\|\|` / `$( )` / backtick / var-indirect `rm -rf /` | block, same rule | TJ-GAP-053 escape hardening holds |
| `echo … \| base64 -d \| sh` | block, `builtin-indirect-shell` | holds |
| `curl -s URL \| sh` | block, `builtin-curl-pipe-shell` | holds |
| `sudo echo hi` | block, `builtin-sudo` | holds |
| `cat /etc/passwd` | **allow, rule_id null** | default-allow; `allow-cat-safe` does NOT match (DF-13) |
| `chmod 777 ~/work` | allow | tilde-relative escapes the absolute-path rule (known, DF-7 still open) |
| `ls \| grep secret` | allow | unmatched → default-allow, no provenance (DF-12) |

**The finding that matters for integrators:** the firewall is a
*deny-list over a default-allow*. Unmatched commands are allowed, and an
allow verdict never says *which* rule (if any) produced it. Nothing in
README/quickstart/specs states the default verdict. Filed as
**DF-TERMINAL-JAIL-12**.

### 2.2 The CLI end-to-end (execution layer)

Host class: `pidns-capability-probe.py` → **DEGRADED**;
`fs-isolation-probe.py` → DEGRADED (AppArmor `unprivileged_userns` denies
setgid/setgroups; remediation text printed, always exit 0 — good UX).

| Flow | Result |
|---|---|
| bare mode `terminal-jail echo hi` | exit 2, fail-closed, honest message ✓ |
| `--user echo "in jail"` | rc=0 + loud `no filesystem isolation` warning ✓ (TJ-DF-015 fix verified) |
| `--user sh -c 'id -u'` | 65534, env scrubbed (USER=nobody, HOME=/nonexistent) ✓ |
| enforce block (`sudo echo hi`) | COMMAND BLOCKED box, rc=126 ✓ |
| **warn mode without `--user`** | WARN line prints FIRST, then rc=2 — **TJ-DF-016 fix VERIFIED** (warn no longer dies silent) |
| **auto-sandbox (`./script.sh`, `uv run pytest`)** | `[terminal-jail] Modified: … → sandboxed` then **rc=2, command never runs** → **DF-TERMINAL-JAIL-11 (NEW P1)** |

DF-11 detail — this is the sharpest finding of the run: on this host the
bridge's modify verdict prepends `unshare --user --pid --fork
--kill-child=SIGKILL bash -c …` — flags that **succeed** when invoked via
`--user` (rc=0, same session, same host). The wrapper's bare-mode preflight
(`standalone/terminal-jail:366`) exits 2 before the
already-prefixed-command branch (`:386`) can run. So all 8 auto-sandbox
classes (`make`, `pytest`, `go test`, `pip install`, `cargo`, `gcc`,
`npm test`, script execution) are dead end-to-end on DEGRADED hosts, and
SKILL.md pitfall 7 still claims the nested namespace works here — stale.

### 2.3 TJ-DF-015 re-probe (documented degraded behavior, not a bug)

Confirmed again at HEAD: jail-created files owned `kara(1000)`, jailed
process reads mode-600 caller files. This is the DOCUMENTED `=degraded`
tier on this host (uid mapping denied by AppArmor) — the CLI warns loudly.
Honest docs; not refiled. On a FULL/mapped host the mapping makes DAC real.

### 2.4 Install path (fresh-machine leg, local)

`TERMINAL_JAIL_INSTALL_DIR=/tmp/… ./install.sh` → 1s, scratch prefix only;
**live `~/.config/terminal-jail/rules.d/00-builtins.yaml` mtime unchanged**
→ **DF-TERMINAL-JAIL-8 fix VERIFIED** (a scratch install no longer mutates
live config). Installed binary reports 1.1.0 and runs.

**Bunker leg: SKIPPED with evidence (DF-TERMINAL-JAIL-14).** Two
`bunker spawn --server bunker-las-03` attempts → `deadline_exceeded`;
`bunker list` → no agents; root-ssh shows my half-spawned users with no
rootless docker socket (install step never completes) — a regression vs the
09-15 run where this leg passed. Host itself healthy (bunkerd active,
docker 26.1.5, outbound 200). Half-spawned users cleaned up; 3 pre-existing
stale users noted, not mine, left alone. Infra follow-up needed; local
scratch install is the only installability evidence this run.

## 3. What works, what a new user must know

1. **Probe first.** `pidns-capability-probe.py` and `fs-isolation-probe.py`
   classify the host (both exit 0). Branch on them: FULL → bare mode;
   DEGRADED → `--user` for execution, and expect auto-sandbox to be
   unavailable until DF-11 lands.
2. **Test rules through the bridge, never by executing.** The bridge is a
   safe oracle — no command runs.
3. **Read the `[bridge-error]` reason.** Fail-open is the contract for
   malformed input; treat any reason starting `[bridge-error]` as a denial
   in your own harness if you need fail-closed.
4. **`--user` = PID containment + env scrub ONLY on unmapped hosts** —
   file permissions still evaluate as the caller (TJ-DF-015 docs; the
   `no filesystem isolation` warning is the tell).
5. **Default-allow is the posture.** The blocklist denies specific
   patterns; everything else is allowed and looks identical to an
   allowlist hit (until DF-12 adds provenance).
6. **Counts in prose drift; the YAML is truth.** `rules/00-builtins.yaml`
   parses to 39 rules (21 block / 8 sandbox / 10 allow) vs README's "30
   (12/8/10)" — DF-9 still open, third run in a row seeing it.

## 4. Friction log (chronological, evidence-first)

1. My own gateway hardline blocked the first probe batch (literal `rm -rf /`
   tokens as bridge DATA) — had to build payload strings at runtime in a
   scratch script. Same friction the 08-19 run hit; the SKILL.md pitfall 8
   already covers it (documented, worked around in 2 min).
2. `chmod 777 ~/work` allowed while any absolute path blocks (known DF-7).
3. `cat /etc/passwd` allowed with no rule, no reason, no docs of the default
   verdict (new DF-12/13).
4. Auto-sandbox rc=2 with a *namespace* error message for what is actually a
   wrapper-ordering bug (new DF-11 — the error text misattributes the cause).
5. Bunker spawn deadline ×2 → install leg skipped (DF-14, infra).

## 5. Verdict rationale

The promise **holds for the documented paths**: block rules are strong and
escape-hardened, schema errors are honest, degradation is loud, install is
scoped and fast, and 420 tests pass in 15s. It **does not hold for the
auto-sandbox path** on this host class (DF-11) — the feature the firewall
advertises for everyday commands (`make`, `pytest`, scripts) cannot
complete — and the firewall's core semantic (default-allow, no allow
provenance) is undocumented (DF-12). Both are fixable without design
change, hence PROMISING-BUT-ROUGH rather than DOES-NOT-DELIVER.

## 6. Filed this run

| ID | P | One-liner |
|---|---|---|
| DF-TERMINAL-JAIL-11 | P1 | auto-sandbox dead-ends on DEGRADED hosts (preflight precedes prefixed-exec branch) |
| DF-TERMINAL-JAIL-12 | P1 | default-allow undocumented; allow verdicts carry no rule provenance |
| DF-TERMINAL-JAIL-13 | P2 | allow-cat-safe negative lookahead can never exclude /etc|/boot|/proc|/sys — rule is a no-op where it claims to matter |
| DF-TERMINAL-JAIL-14 | P2 | SKIPPED-install-bunker: las-bunker-03 spawn broken (deadline ×2, no rootless docker); infra owner |

Re-verified fixed this run: DF-6 (schema markers), DF-8 (install scope),
TJ-DF-015 (loud warn + honest docs), TJ-DF-016 (warn line precedes
preflight). Still open from prior runs: DF-7, DF-9, DF-10, TJ-GAP-058..062.
