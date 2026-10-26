# Verdict: TJ-DF-046

**Task:** Egress tier: engage Landlock on plain-allow verdicts
**Evaluated:** 2026-10-18T11:39:58.422444
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ 1. A rule_id=null (allow) verdict with TERMINAL_JAIL_LANDLOCK_NET=1 MUST either engage the net tier (landlock-net-loader) and enforce egress blocking, or print a loud degrade warning naming the cause — never silently run the payload CONNECTED. 2. README documented example (python3 -c socket.connect to non-allowlisted port) must NOT succeed CONNECTED under the installed CLI. 3. A contract test verifies: plain-allow command to blocked port prints a degrade warning or is blocked.: PASS: standalone/terminal-jail:147-160 resolves landlock-net-loader.py; :1046-1068 _tj_egress_tier_decide sets TJ_EGRESS_TIER_ATTACH or calls _tj_egress_degrade (loud WARNING naming cause + searched paths); called at :1100 (composed), :1253/:1262 (seccomp trampoline), :1298/:1338 (bwrap/unshare). Live run (plain-allow verdict action=allow rule_id=null): knob=0 -> CONNECTED (control); knob=1 -> "landlock-net: kernel egress tier APPLIED ... TCP connect() restricted to ports [22,53,80,443]" then PermissionError [Errno 13], no CONNECTED.
Partial verdict — all verified criteria passed

## Summary

Judge Result: TJ-DF-046

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ 1. A rule_id=null (allow) verdict with TERMINAL_JAIL_LANDLOCK_NET=1 MUST either engage the net tier (landlock-net-loader) and enforce egress blocking, or print a loud degrade warning naming the cause — never silently run the payload CONNECTED. 2. README documented example (python3 -c socket.connect to non-allowlisted port) must NOT succeed CONNECTED under the installed CLI. 3. A contract test verifies: plain-allow command to blocked port prints a degrade warning or is blocked.: PASS: standalone/terminal-jail:147-160 resolves landlock-net-loader.py; :1046-1068 _tj_egress_tier_decide sets TJ_EGRESS_TIER_ATTACH or calls _tj_egress_degrade (loud WARNING naming cause + searched paths); called at :1100 (composed), :1253/:1262 (seccomp trampoline), :1298/:1338 (bwrap/unshare). Live run (plain-allow verdict action=allow rule_id=null): knob=0 -> CONNECTED (control); knob=1 -> "landlock-net: kernel egress tier APPLIED ... TCP connect() restricted to ports [22,53,80,443]" then PermissionError [Errno 13], no CONNECTED.
Partial verdict — all verified criteria passed

Overall: PASS ✓
