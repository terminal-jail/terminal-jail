# Dogfood Run 11 — Operator/Maintainer Tooling (2026-09-25)

**Angle:** the operator-facing tooling in `scripts/` — surfaces untouched by
runs 1–10 (firewall CLI, rule packs live, JSON bridge library, deploy shim,
seccomp, plugin, install/uninstall all covered before). A terminal-jail
OPERATOR on a fleet is the user here, not an integrator.

**Promise under test:** "A terminal-jail operator can verify their host is not
silently running stale rules (`rules-drift-probe.py`), regenerate/check the
rule catalog after edits (`rule-catalog.py`), author and validate a new rule
pack (`rule-pack-tool.py`), see their consciously-allowed GTFOBins surface
(`gtfobins-sweep.py`), watch kernel compatibility (`kernel-watchdog.sh`), and
export metrics (`metrics-export.py`) — using only the documented commands."

**Verdict: PROMISING-BUT-ROUGH.** Every gate works and — more important —
every gate's NEGATIVE path works: the probes actually catch what they claim to
catch, proven by inducing the failures they exist to detect. The rough edges
are all in the metrics story (structurally dead) and the custom-pack story
(validated but uninstallable).

---

## 1. What was actually done (real operator workflow)

1. Ran all six tools bare on this host. All rc=0:
   - `rule-catalog.py --check` → `OK — 55 rules (36 block / 9 sandbox / 10 allow)`
   - `rules-drift-probe.py` → `OK: no installed override … drift=0 overridden=54`
   - `rule-pack-tool.py list` → `db … 14`
   - `metrics-export.py --json` → all counters 0 (see finding 1)
   - `kernel-watchdog.sh` (+ `--json`) → HEALTHY, state file written, gitignored
   - `gtfobins-sweep.py` → `25/25 postures match (100.0%)`, `review backlog: 26`

2. **Authored a real custom rule pack** (`pack-ops.yaml`: a block rule for
   absolute-path recursive `rm`, a warn rule for `curl … | sh`), validated it
   with `rule-pack-tool.py`, and exercised enforcement live through
   `terminal-jail --interruptor` and the bridge.

3. **Induced the failure each probe exists to catch**, in scratch dirs via the
   documented `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR` env resolution
   (live config never touched):
   - flipped `builtin-rm-rf-root` `block → sandbox` in a copy of the installed
     mirror → drift probe printed `DRIFT: builtin-rm-rf-root: engine
     action=block installed action=sandbox (weaker)` with both file paths;
     `--fail-on-drift` exited 1;
   - confirmed the drift is REAL, not cosmetic: with the weakened mirror the
     bridge returns `"action": "modify"` (auto-sandbox — the command runs) for
     `rm -rf /`, vs `"action": "block"` with the healthy mirror. This is the
     TJ-GAP-069 property re-proven live on the v1.2.0 engine;
   - flipped the sudo/shell posture `blocked → allowed-conscious` in a copy of
     the GTFOBins seed → `gtfobins-sweep.py --check` exited 1 with
     `DRIFT-OVERBLOCKED  sudo/shell … live=block rule=builtin-sudo`.

4. **Validator negative battery (6/6 refused, each with a precise one-line
   reason and exit 2):** non-dispatchable match type; id outside
   `pack-<name>-*` namespace; duplicate id inside the pack; invalid action;
   collision with an engine builtin id; pattern rule with empty pattern.
   A valid pack passes with a full summary line naming its destination.

5. Perf (Step 2b): drift probe 64.3 ms ± 4.9 (hyperfine 20 runs), cold 60 ms;
   catalog `--check` 0.21 s; gtfobins sweep 0.09 s; pack validate 0.06 s.
   Nothing here is slow enough for a user to notice — **no PERF row**, and we
   say so per the skill's law.

## 2. Findings (board rows TJ-DF-033..036)

| ID | P | Finding |
|----|---|---------|
| TJ-DF-033 | P2 | **metrics-export.py can only ever export zeros.** `plugin/terminal_jail/plugin.py` defines the `Metrics` dataclass (9 counters) and `get_metrics()`/`reset_metrics()`, but there is no increment site anywhere in non-test code (grep across the repo: the only references outside tests are the dataclass itself and the exporter). The plugin's hooks (`_on_pre_tool_call`) log but never count. Every field of the exported JSON is structurally 0 forever; `test_metrics_export.py` passes by asserting the shape of zeros. README's "observability (metrics, logging)" promise is currently a stub with a polished CLI on top. |
| TJ-DF-034 | P2 | **A validator-approved custom pack has no install path.** `rule-pack-tool.py validate` exists precisely to vet packs before the installer writes them (TJ-GAP-061), but `install.sh --rule-pack <name>` installs only packs shipped in the repo checkout; there is no `--rule-pack-file`/external-pack path. The validator's own success output names the intended destination (`~/.config/terminal-jail/rules.d/terminal-jail-pack-ops.yaml`) that no documented command writes. Workaround was a hand `cp` — which nothing then checks (drift probe exempts non-builtin ids by design, uninstall treats packs as installer-managed). |
| TJ-DF-035 | P2 | **Pack-authoring schema is learnable only from source.** First four authoring attempts were all refused on `match.type 'regex' is not dispatchable` — the valid types (9 of them) appear only in the refusal message and in specs/interruptor.md §3.4; the README's Rule-packs section covers install/remove of shipped packs only; `--help` teaches no schema. The validator is a great backstop; there is no front-door documentation. Suggested fix: a `rule-pack-tool.py schema` / example-pack output or a short "authoring a pack" section. |
| TJ-DF-036 | P2 | **SKIPPED-install-bunker — all three bunker hosts down this tick.** las-bunker-03: ssh connect timeout to its tailnet address. las-bunker-04: ssh connect timeout. las-bunker-02: reachable, but `systemctl is-active bunkerd` = `activating` (crash loop), root cause from `journalctl -u bunkerd`: `refusing to start: refusing to bind non-loopback plaintext listener :10002, :10001: set tls.enabled: true to serve TLS, or explicitly set tls.insecure_dev: true` — restart counter at 26,012. No install path could be tested this run. (Two separate infra issues: las-02 config/binary drift; las-03/04 network reachability.) |

**Friction count: 3** (schema discovery dead-end ×1, no custom-pack install
path ×1, `--exec`/flag-form confusion on first use — my error, correct form is
`--interruptor <command>`, documented in `--help`; noted because the allow
path's failure mode `exec: <cmd>: not found` reads like a broken tool rather
than a wrong invocation).

## 3. The right way (for the next operator)

```bash
# host hygiene, one command each — all safe to cron:
python3 scripts/rule-catalog.py --check          # docs vs rules drift (repo)
python3 scripts/rules-drift-probe.py --fail-on-drift   # installed-mirror drift (host) — CI/gate form
python3 scripts/kernel-watchdog.sh --json        # kernel compat (state file is gitignored)
python3 scripts/gtfobins-sweep.py --check        # conscious-allow surface (repo)
python3 scripts/rule-pack-tool.py list           # what this checkout ships

# custom pack, end to end (today): validate → hand-copy → test live → remove
python3 scripts/rule-pack-tool.py validate pack.yaml --pack-name ops
cp pack.yaml ~/.config/terminal-jail/rules.d/terminal-jail-pack-ops.yaml
terminal-jail --interruptor echo ok              # engine loads it (drift probe lists it as non-builtin info)
rm ~/.config/terminal-jail/rules.d/terminal-jail-pack-ops.yaml

# prove a rule fires WITHOUT trusting your eyes on a wall of output:
echo '{"command": "rm -rf /"}' | python3 plugin/terminal_jail/interruptor_bridge.py
#   → {"action": "...", "rule_id": "..."} — the bridge is the honest oracle
```

Env-var scratch testing (no live-config risk): point
`TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR` at a scratch copy of the rules dir —
the drift probe resolves it exactly like the engine.

## 4. Time-to-first-success

~4 minutes for the six bare tools; ~35 minutes to the first full custom-pack
cycle (validate → enforce → prove via bridge), of which ~15 min was schema
discovery from source (finding TJ-DF-035).
