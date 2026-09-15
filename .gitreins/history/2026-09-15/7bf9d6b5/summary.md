# Verdict: TJ-DF-017

**Task:** Branch quickstart/skill verify flow on the pidns capability probe (FULL vs DEGRADED)
**Evaluated:** 2026-09-15T18:19:33.898442
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m1:18PM[0m [32mINF[0m [1mscanned ~3329741 bytes (3.33 MB) in 346ms[0m
[90m1:18PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ grep -n pidns-capability-probe docs/quickstart.md shows >=1 hit inside the section 3a verify block: grep -n pidns-capability-probe docs/quickstart.md → line 53: `python3 scripts/pidns-capability-probe.py`, inside §3a 'Step 1 — classify the host' verify block (lines 50-58) which documents FULL/DEGRADED/UNKNOWN and exit 0.
  ✓ quickstart 3a has an explicit FULL branch (bare mode + readlink /proc/self/ns/pid differs from host) and a DEGRADED branch stating what --user does and does not contain: docs/quickstart.md §3a: `FULL` branch (lines 63-72) runs bare `~/.local/bin/terminal-jail echo "in jail"` and `~/.local/bin/terminal-jail sh -c 'readlink /proc/self/ns/pid'` with comment '→ a DIFFERENT inode than the host line above = PID-namespace containment' vs host `readlink /proc/self/ns/pid # host: pid:[4026531836]`. `DEGRADED` branch (lines 74-88) states bare mode exits 2 fail-closed with no fallback, `--user` lands in a new pidns (host 4026531836 → jail 4026538825), scrubs identity env (nobody/nobody//nonexistent), but 'the host PID view stays exposed (no private /proc mount — PID 1 is still the host's systemd) and there is no filesystem isolation unless a uid mapping can be created'.
  ✓ grep -n pidns-capability-probe skills/terminal-jail-usage/SKILL.md shows >=1 hit in the Quick start block and the --user echo line no longer implies containment by itself: grep -n pidns-capability-probe skills/terminal-jail-usage/SKILL.md → line 44: `python3 scripts/pidns-capability-probe.py        # FULL | DEGRADED | UNKNOWN, exit 0`, inside the '## Quick start' bash block (lines 41-56). Line 48: `$TJ --user echo hi                               # exec + rc=0 only — NOT containment proof` — explicitly disclaims containment; containment is attributed to the inode comparison on line 47.
  ✓ every command in the changed doc regions runs verbatim on this host with the documented result: After the documented §3a prerequisite `./install.sh` (rc=0, installs ~/.local/bin/terminal-jail): `--version` → 'terminal-jail 1.1.0' rc=0; `python3 scripts/pidns-capability-probe.py` → 'DEGRADED' rc=0; `readlink /proc/self/ns/pid` → pid:[4026531836] (matches doc host value); DEGRADED bare `terminal-jail echo "in jail"` → rc=2 with 'terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user' (matches doc); `--user sh -c 'readlink /proc/self/ns/pid'` → pid:[4026538827] rc=0, different inode from host (doc's literal 4026538825 differs but doc states 'The jailed inode value changes per invocation — the check is the inequality, not a literal'); `--user sh -c 'echo "$USER $LOGNAME $HOME"'` → 'nobody nobody /nonexistent' (matches doc); `terminal-jail rm -rf /` → COMMAND BLOCKED box rc=126 (matches doc); `python3 scripts/fs-isolation-probe.py` → 'DEGRADED: mapped launch failed...' rc=0 (matches doc). SKILL.md: `$TJ --user echo hi` → 'hi' rc=0; `$TJ --user bash -c 'exit 7'` → 7; `echo hi | $TJ --user cat` → 'hi'; `$TJ --user fdisk /dev/sda` → rc=126; warn/disabled/--no-interruptor variants → firewall off (rc=1 from fdisk itself). All consistent with documented results.
  ✓ uvx ruff check . exits 0 and .venv/bin/python -m pytest plugin -q stays at 348 passed/14 skipped: `uvx ruff check .` → 'All checks passed!' exit_code=0. `.venv/bin/python -m pytest plugin -q` → '348 passed, 14 skipped in 10.51s' — exactly the required 348 passed / 14 skipped.
All five criteria pass: the pidns capability probe is wired into both docs' verify blocks with explicit FULL/DEGRADED branches, the --user echo line is relabelled as non-containment, every documented command reproduces its documented result live, and ruff exits 0 with pytest at 348 passed/14 skipped.

## Summary

Judge Result: TJ-DF-017

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m1:18PM[0m [32mINF[0m [1mscanned ~3329741 bytes (3.33 MB) in 346ms[0m
[90m1:18PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ grep -n pidns-capability-probe docs/quickstart.md shows >=1 hit inside the section 3a verify block: grep -n pidns-capability-probe docs/quickstart.md → line 53: `python3 scripts/pidns-capability-probe.py`, inside §3a 'Step 1 — classify the host' verify block (lines 50-58) which documents FULL/DEGRADED/UNKNOWN and exit 0.
  ✓ quickstart 3a has an explicit FULL branch (bare mode + readlink /proc/self/ns/pid differs from host) and a DEGRADED branch stating what --user does and does not contain: docs/quickstart.md §3a: `FULL` branch (lines 63-72) runs bare `~/.local/bin/terminal-jail echo "in jail"` and `~/.local/bin/terminal-jail sh -c 'readlink /proc/self/ns/pid'` with comment '→ a DIFFERENT inode than the host line above = PID-namespace containment' vs host `readlink /proc/self/ns/pid # host: pid:[4026531836]`. `DEGRADED` branch (lines 74-88) states bare mode exits 2 fail-closed with no fallback, `--user` lands in a new pidns (host 4026531836 → jail 4026538825), scrubs identity env (nobody/nobody//nonexistent), but 'the host PID view stays exposed (no private /proc mount — PID 1 is still the host's systemd) and there is no filesystem isolation unless a uid mapping can be created'.
  ✓ grep -n pidns-capability-probe skills/terminal-jail-usage/SKILL.md shows >=1 hit in the Quick start block and the --user echo line no longer implies containment by itself: grep -n pidns-capability-probe skills/terminal-jail-usage/SKILL.md → line 44: `python3 scripts/pidns-capability-probe.py        # FULL | DEGRADED | UNKNOWN, exit 0`, inside the '## Quick start' bash block (lines 41-56). Line 48: `$TJ --user echo hi                               # exec + rc=0 only — NOT containment proof` — explicitly disclaims containment; containment is attributed to the inode comparison on line 47.
  ✓ every command in the changed doc regions runs verbatim on this host with the documented result: After the documented §3a prerequisite `./install.sh` (rc=0, installs ~/.local/bin/terminal-jail): `--version` → 'terminal-jail 1.1.0' rc=0; `python3 scripts/pidns-capability-probe.py` → 'DEGRADED' rc=0; `readlink /proc/self/ns/pid` → pid:[4026531836] (matches doc host value); DEGRADED bare `terminal-jail echo "in jail"` → rc=2 with 'terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user' (matches doc); `--user sh -c 'readlink /proc/self/ns/pid'` → pid:[4026538827] rc=0, different inode from host (doc's literal 4026538825 differs but doc states 'The jailed inode value changes per invocation — the check is the inequality, not a literal'); `--user sh -c 'echo "$USER $LOGNAME $HOME"'` → 'nobody nobody /nonexistent' (matches doc); `terminal-jail rm -rf /` → COMMAND BLOCKED box rc=126 (matches doc); `python3 scripts/fs-isolation-probe.py` → 'DEGRADED: mapped launch failed...' rc=0 (matches doc). SKILL.md: `$TJ --user echo hi` → 'hi' rc=0; `$TJ --user bash -c 'exit 7'` → 7; `echo hi | $TJ --user cat` → 'hi'; `$TJ --user fdisk /dev/sda` → rc=126; warn/disabled/--no-interruptor variants → firewall off (rc=1 from fdisk itself). All consistent with documented results.
  ✓ uvx ruff check . exits 0 and .venv/bin/python -m pytest plugin -q stays at 348 passed/14 skipped: `uvx ruff check .` → 'All checks passed!' exit_code=0. `.venv/bin/python -m pytest plugin -q` → '348 passed, 14 skipped in 10.51s' — exactly the required 348 passed / 14 skipped.
All five criteria pass: the pidns capability probe is wired into both docs' verify blocks with explicit FULL/DEGRADED branches, the --user echo line is relabelled as non-containment, every documented command reproduces its documented result live, and ruff exits 0 with pytest at 348 passed/14 skipped.

Overall: PASS ✓
