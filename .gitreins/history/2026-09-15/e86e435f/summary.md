# Verdict: QA-TERMINAL-JAIL-4

**Task:** Bunker blocker lifted: 0.1.4 deployed with the pool fix, live spawn proven
**Evaluated:** 2026-09-15T02:41:25.409413
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: 
  ✓ secrets: [90m9:35PM[0m [32mINF[0m [1mscanned ~4589307 bytes (4.59 MB) in 373ms[0m
[90m9:35PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P
- ✓ **tier2**
  - COMPLETE
  ✓ bunker status --server bunker-las-02 reports Version 0.1.4 ONLINE with the kara-lair agent running, contradicting the 0.1.3/4af949d build cited in QA-TERMINAL-JAIL-4: Ran `cd /home/kara/bunker && ./bunker status --server bunker-las-02` -> 'Version: 0.1.4', 'Status: ONLINE', 'Agents: 1/8', 'Docker: 1 containers', uptime 1d15h (exit 0). `./bunker list --server bunker-las-02` -> 'kara-lair running 1% (693.3 MB/64.0 GB) 2026-08-23T03:03:12Z', Total: 1 agents. `./bunker info kara-lair` -> Status: running, Port Range 30000-30099. This contradicts the 0.1.3/4af949d build cited in the task.
  ✓ In the bunker source repo git tag --contains b4c3c48 and git tag --contains 2c67b47 both list v0.1.4 (tag commit cef10fc), proving the QA-BUNKER-4 port-range-free fix ships inside the deployed release line: In /home/kara/bunker: `git tag --contains b4c3c48` -> v0.1.4; `git tag --contains 2c67b47` -> v0.1.4. `git rev-parse v0.1.4` = 3c78161dacb49f98c7b89c1f91629964fd035294 and `git log -1 v0.1.4` = cef10fc 'chore: release v0.1.4 — GAP-070 durable agent registry'. `git merge-base --is-ancestor` confirms both are ancestors of v0.1.4. b4c3c48 = 'QA-BUNKER-4: free port range on non-force destroy not_found path'; 2c67b47 = 'fix(agent): free port range on failed spawn — capacity check before Allocate'.
  ✓ A live spawn on bunker-las-02 succeeded while agent kara-lair held its range (port range 30600-30699 allocated) and destroy removed the probe agent, so the deterministic pool exhausted: 1 ranges failure no longer reproduces: Independently reproduced live: `bunker spawn --server bunker-las-02 --ttl 20m` SUCCEEDED while kara-lair held its range; new agent 87948bfb created 2026-09-14T19:39:33-07:00. `bunker info 87948bfb` -> 'Port Range: 30600-30699' (exact match). `bunker destroy 87948bfb --server bunker-las-02` -> 'Agent 87948bfb destroyed.' + 'Removed local SSH key' (exit 0). `bunker list` -> back to exactly 1 agent (kara-lair). No 'pool exhausted: 1 ranges' failure occurred. Board foreman_notes on rows -3/-4/-5 record the same evidence (agent ab208082, port range 30600-30699).
  ✓ Board rows QA-TERMINAL-JAIL-1, -3, -4 and -5 carry status complete plus a foreman_note with that evidence, and scripts/board_id_guard.py still reports 110 rows / 110 unique ids with rc=0: /home/kara/terminal-jail/.coding-hermes/board/tasks.jsonl: line 106 QA-TERMINAL-JAIL-1 status=complete + foreman_note (1432 chars); line 94 QA-TERMINAL-JAIL-3 complete + note (1059); line 95 QA-TERMINAL-JAIL-4 complete + note (1059); line 97 QA-TERMINAL-JAIL-5 complete + note (1059). Notes contain the evidence (0.1.4/ONLINE, git tag --contains b4c3c48/2c67b47 = v0.1.4 cef10fc, live spawn port range 30600-30699 agent ab208082 + destroy). Committed in cd12c7a (tick #275). `cd /home/kara/terminal-jail && .venv/bin/python scripts/board_id_guard.py` -> 'rows: 110 / OK: 110 rows, 110 unique ids', RC=0. Project test suite also green: `pytest -x --tb=short -q` -> '334 passed, 13 skipped in 7.04s', rc=0.
All four criteria verified with live evidence: bunker-las-02 runs 0.1.4 ONLINE with kara-lair, both fix commits are contained in tag v0.1.4 (cef10fc), a live spawn/destroy cycle reproduced successfully with port range 30600-30699 and no pool exhaustion, and all four board rows are complete with evidence notes while board_id_guard.py reports 110/110 unique ids at rc=0.

## Summary

Judge Result: QA-TERMINAL-JAIL-4

Stage tier1: PASS
    ✓ lint: 
  ✓ secrets: [90m9:35PM[0m [32mINF[0m [1mscanned ~4589307 bytes (4.59 MB) in 373ms[0m
[90m9:35PM[0m [32m
  ✓ tests: ============================= test session starts ==============================
platform linux -- P

Stage tier2: PASS
  COMPLETE
  ✓ bunker status --server bunker-las-02 reports Version 0.1.4 ONLINE with the kara-lair agent running, contradicting the 0.1.3/4af949d build cited in QA-TERMINAL-JAIL-4: Ran `cd /home/kara/bunker && ./bunker status --server bunker-las-02` -> 'Version: 0.1.4', 'Status: ONLINE', 'Agents: 1/8', 'Docker: 1 containers', uptime 1d15h (exit 0). `./bunker list --server bunker-las-02` -> 'kara-lair running 1% (693.3 MB/64.0 GB) 2026-08-23T03:03:12Z', Total: 1 agents. `./bunker info kara-lair` -> Status: running, Port Range 30000-30099. This contradicts the 0.1.3/4af949d build cited in the task.
  ✓ In the bunker source repo git tag --contains b4c3c48 and git tag --contains 2c67b47 both list v0.1.4 (tag commit cef10fc), proving the QA-BUNKER-4 port-range-free fix ships inside the deployed release line: In /home/kara/bunker: `git tag --contains b4c3c48` -> v0.1.4; `git tag --contains 2c67b47` -> v0.1.4. `git rev-parse v0.1.4` = 3c78161dacb49f98c7b89c1f91629964fd035294 and `git log -1 v0.1.4` = cef10fc 'chore: release v0.1.4 — GAP-070 durable agent registry'. `git merge-base --is-ancestor` confirms both are ancestors of v0.1.4. b4c3c48 = 'QA-BUNKER-4: free port range on non-force destroy not_found path'; 2c67b47 = 'fix(agent): free port range on failed spawn — capacity check before Allocate'.
  ✓ A live spawn on bunker-las-02 succeeded while agent kara-lair held its range (port range 30600-30699 allocated) and destroy removed the probe agent, so the deterministic pool exhausted: 1 ranges failure no longer reproduces: Independently reproduced live: `bunker spawn --server bunker-las-02 --ttl 20m` SUCCEEDED while kara-lair held its range; new agent 87948bfb created 2026-09-14T19:39:33-07:00. `bunker info 87948bfb` -> 'Port Range: 30600-30699' (exact match). `bunker destroy 87948bfb --server bunker-las-02` -> 'Agent 87948bfb destroyed.' + 'Removed local SSH key' (exit 0). `bunker list` -> back to exactly 1 agent (kara-lair). No 'pool exhausted: 1 ranges' failure occurred. Board foreman_notes on rows -3/-4/-5 record the same evidence (agent ab208082, port range 30600-30699).
  ✓ Board rows QA-TERMINAL-JAIL-1, -3, -4 and -5 carry status complete plus a foreman_note with that evidence, and scripts/board_id_guard.py still reports 110 rows / 110 unique ids with rc=0: /home/kara/terminal-jail/.coding-hermes/board/tasks.jsonl: line 106 QA-TERMINAL-JAIL-1 status=complete + foreman_note (1432 chars); line 94 QA-TERMINAL-JAIL-3 complete + note (1059); line 95 QA-TERMINAL-JAIL-4 complete + note (1059); line 97 QA-TERMINAL-JAIL-5 complete + note (1059). Notes contain the evidence (0.1.4/ONLINE, git tag --contains b4c3c48/2c67b47 = v0.1.4 cef10fc, live spawn port range 30600-30699 agent ab208082 + destroy). Committed in cd12c7a (tick #275). `cd /home/kara/terminal-jail && .venv/bin/python scripts/board_id_guard.py` -> 'rows: 110 / OK: 110 rows, 110 unique ids', RC=0. Project test suite also green: `pytest -x --tb=short -q` -> '334 passed, 13 skipped in 7.04s', rc=0.
All four criteria verified with live evidence: bunker-las-02 runs 0.1.4 ONLINE with kara-lair, both fix commits are contained in tag v0.1.4 (cef10fc), a live spawn/destroy cycle reproduced successfully with port range 30600-30699 and no pool exhaustion, and all four board rows are complete with evidence notes while board_id_guard.py reports 110/110 unique ids at rc=0.

Overall: PASS ✓
