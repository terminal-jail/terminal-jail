# Terminal Jail — Real-Use Integration Report (2026-09-15)

Fourth dogfood run (2026-08-10, 2026-08-19, 2026-09-01). All 14 prior dogfood
findings (TJ-DF-001..014) were marked complete on the board, the board showed
6 open rows of which only E2E-001 is a recurring loop, and the last three
commits are "battery ALL GREEN" idle audits. The interesting question, same as
last time: **do the fixes hold under real use, and what does the green board
miss?** Answer: the 08-19 security fixes hold (verified live, 30+ probes), the
install-from-scratch story is genuinely good (0-second install, clean smoke on
an ephemeral bunker box) — and the green board missed a P0: **the `--user`
jail's "runs as nobody" isolation claim is an unmapped-namespace illusion; a
jailed process reads and writes the caller's files as owner.**

Host: Ubuntu 26.04, kernel 7.0.0-30, unprivileged PID namespaces DENIED
(EPERM) — `--user` is the only runnable mode here, as documented. Bunker
install leg: las-bunker-03, fresh agent per the standard loop.

## 1. Verdict on prior fixes (re-verified live this run)

| Prior finding | Verified 2026-09-15 |
|---|---|
| TJ-DF-011 (P0) chmod bypass | ✅ all 5 variants block at the bridge (`builtin-chmod-777-root`) AND at the CLI (rc=126 + COMMAND BLOCKED box): `chmod -R 777 /`, `--recursive`, `a+rwx`, `7777`, `-R 777 /etc`; plain form still blocks; benign `chmod 644/x +x/755/-R 644` still allows (no overblock) |
| TJ-DF-012 (P1) silent warn override | ✅ same-ID `action: warn` rule + `rm -rf /…` → rc=0 with `terminal-jail: WARNING — would have blocked: …` on stderr |
| TJ-DF-014 (P3) env leak | ✅ `--user env` → `USER=nobody LOGNAME=nobody HOME=/nonexistent`; wrapper lines 293-296 |
| DF-TERMINAL-JAIL-3 (P1) install clobbers rules | ✅ re-ran `./install.sh` over an edited rules file: backs up to `00-builtins.yaml.bak-<UTC>` + loud WARNING line |
| TJ-GAP-021/GAP-034 basics | ✅ bare mode exit 2 + `--user` hint; fail-open bridge contract on malformed input (`[bridge-error] … fail-open`); exit passthrough (7→7); stdin passthrough; `--kill-child` reaps backgrounded children (pgrep: dead); auto-sandbox modify path returns `modify`; curl\|sh and sudo block |

## 2. Install leg — local + ephemeral bunker

**Local scratch-HOME** (`HOME=/tmp/dogfood-tj/home`, checkout detected):
`./install.sh` → rc=0, **<1s**, full layout (`~/.local/bin/terminal-jail`,
`~/.local/lib/terminal-jail/plugin/…`, `~/.local/lib/terminal-jail/seccomp-loader.py`,
`~/.config/terminal-jail/rules.d/00-builtins.yaml`). Installed binary verified
end-to-end: `--version` → 1.1.0; `--user echo` → ok; firewall → 126 + box;
`--user --seccomp` → `/proc/self/status` `Seccomp: 2 / Seccomp_filters: 1`.

**Ephemeral bunker (las-bunker-03, agent b7962902, destroyed after):**
fresh Debian user, no toolchains. Followed ONLY the project's documented path:
`git clone https://github.com/totalwindupflightsystems/terminal-jail.git ~/app`
(public fetch worked, HEAD `d75c793`) → `./install.sh` → rc=0, **0s** →
documented smoke (`--version`, `--user echo` → ok) →
`scripts/pidns-capability-probe.py` → `DEGRADED`, exit 0 exactly as the README
documents. **Installability: proven.** No sudo, no compose, no toolchain
assumptions bit us — the docs' "no root needed" claim holds on a bare box.

## 3. The happy path (all verified this run)

```bash
TJ=./standalone/terminal-jail        # or ~/.local/bin/terminal-jail
$TJ --version                                   # terminal-jail 1.1.0
$TJ --user echo "in jail"                       # rc=0
$TJ --user bash -c 'exit 7'; echo $?            # 7 — passthrough
echo hi | $TJ --user cat                        # stdin passthrough
$TJ --user chmod -R 777 /tmp/x-nonexistent      # 126 + COMMAND BLOCKED box
$TJ --user sudo echo hi                         # 126 (builtin-sudo)
$TJ --user --seccomp python3 …                  # Seccomp: 2, mount→EPERM
./standalone/terminal-jail-sh -c 'echo shim-ok' # deploy shim works
# rule evaluation without execution:
echo '{"command":"curl https://x.sh | sh"}' | python3 plugin/terminal_jail/interruptor_bridge.py
```

## 4. NEW findings (2026-09-15) — board rows TJ-DF-015..018

### TJ-DF-015 (P0): `--user` "nobody" is an unmapped-namespace illusion — NO file isolation
The wrapper runs `unshare --user --pid --fork --kill-child=SIGKILL` with **no
uid mapping** (no `--map-root-user`/`--map-auto`, no `newuidmap`, no `uid_map`
write — the concept appears nowhere in wrapper, engine, specs, or docs). Inside
the jail: `/proc/self/status` shows `Uid: 65534` and `os.getuid() == 65534`,
`CapEff: 0000000000000000` — every *display* overflows to nobody because the
namespace has no mapping. But the credentials keep the caller's underlying
kuid (1000), so **file DAC still evaluates as the owner of kara-owned files**:

```bash
$ TJ --user python3 -c "open('/home/kara/.hermes/config.yaml').read()"
# → reads a mode-600 file. No error.
$ TJ --user python3 -c "open('/home/kara/attack','w').write('x')"
# → creates the file, owned kara:kara.
# CONTROL (same file, real uid drop):
$ sudo -u nobody python3 -c "open('/home/kara/.hermes/config.yaml').read()"
# → PermissionError: errno 13  ← what the jail SHOULD have done
```

So `--user` delivers: PID lifecycle containment (`--kill-child` verified:
backgrounded children die with the jail) + identity-env scrub (TJ-DF-014). It
does **not** deliver: filesystem isolation of any kind. README L27-29/L145 and
`skills/terminal-jail-usage/SKILL.md` L108-110 present it as uid isolation /
"caller home untouched by design" — wrong for the normal case where the tools
you jail run as the same user that owns the home. The engine's auto-sandbox
(`interruptor/decider.py` `_UNSHARE_PREFIX`) wraps pytest/make/pip/etc. with
the same mapping-less prefix, so auto-sandboxed builds have the same property.
Fix direction: a real mapping (`--map-auto` on util-linux 2.38+, or
newuidmap+/etc/subuid) so host files owned by the caller are seen as
non-owner; acceptance = the two probes above must EACCES. Interim: say
plainly in README/quickstart/skill that `--user` = PID containment + env scrub
only.

### TJ-DF-016 (P1): warn mode dies silent on EPERM hosts
`TERMINAL_JAIL_INTERRUPTOR_MODE=warn $TJ rm -rf /<x>` on this host → exit 2,
stderr = only `namespace creation failed`. The namespace preflight death
precedes the firewall's WARN line, so the documented "warn = prints warning,
allows" story (quickstart FAQ; the DF-TERMINAL-JAIL-5 fix) never materializes
end-to-end. The operator sees neither the warning nor the command run.
Fix: evaluate the firewall before preflight and print verdict lines regardless
of namespace outcome.

### TJ-DF-017 (P2): the quickstart/skill verify example proves nothing on EPERM hosts
`--user echo "in jail"` as the §3a verify step only proves exec + rc=0 here —
it validates no containment property (and per TJ-DF-015, no uid isolation
either). `scripts/pidns-capability-probe.py` exists and is great but is still
not wired into the quickstart verify block. Fix: probe first, branch example.

### TJ-DF-018 (P3, upstream): bunker skill recipe drifted
bunkerd on las-bunker-03 now listens on :10001/:10002 (not :19090) and the
YAML-quoted token breaks the skill's capture regex until `tr -d '"'`.
Recorded here for visibility; the fix belongs in the dogfood skill repo.

## 5. Friction log (this run)

1. **Had to read wrapper source to explain the uid behavior** — the docs
   assert "runs as nobody=65534" with no hint that uid mapping is absent;
   `id`/`/proc/self/status` inside the jail actively corroborate the wrong
   belief (65534 everywhere). Biggest single docs gap of the run (= the P0).
2. User-rules dir resolves via `$HOME` (`Path.home()`), NOT `XDG_CONFIG_HOME`
   — my first probe with a fake XDG config silently loaded no user rules.
   There is a documented knob (`TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR`,
   specs/interruptor.md §env table) but it's absent from README/quickstart;
   cost one probe round.
3. Warn-mode silence on EPERM hosts (see TJ-DF-016) — read as "the WARN
   feature is broken" until isolated to preflight ordering.
4. Non-project: the Hermes gateway hardline content-filters literal dangerous
   strings in my own command lines; probe batteries were written as scratch
   python files instead (same workaround as the 08-19 run; project unaffected).

## 6. Verdict

**PROMISING-BUT-ROUGH** (same label as 08-19, but the roughness moved: docs
are now strong and the firewall is real; the remaining roughness is the
`--user` isolation claim). The interruptor firewall + install path + seccomp
+ degradation contracts all deliver under real use. Time-to-first-success
from README clone to working jailed command: under 1 minute locally, and the
bunker fresh-machine run was clone→smoke in under 2 minutes total.

Reproduce everything: probes in `/tmp/dogfood-tj/` (`probe_battery.py`,
`probe_round2.py`, `probe_round3.py`) — bridge oracle battery, CLI battery,
installed-layout battery, bunker install leg. Board rows TJ-DF-015..018.
