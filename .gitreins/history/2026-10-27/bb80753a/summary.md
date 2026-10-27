# Verdict: DF-TERMINAL-JAIL-19

**Task:** [dogfood] restore + verify bunker-las-03 install leg
**Evaluated:** 2026-10-27T09:53:38.642212
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10
- ✓ **tier2**
  - COMPLETE
  ✓ bunker status --server bunker-las-03 reports ONLINE — the row's stated gate for dispatching the install leg: Live re-run: `bunker status --server bunker-las-03` -> 'Version: 0.1.4 / Status: ONLINE', rc=0. foreman_note in .coding-hermes/board/tasks.jsonl:145 records 'bunker status --server bunker-las-03 reported ONLINE (v0.1.4)'; corroborated by .coding-hermes/board/events.jsonl:807 (tick 411) bunker_las03='ONLINE v0.1.4'.
  ✓ A spawn-and-destroy cycle on bunker-las-03 succeeded: the row's foreman_note records the agent id and port range returned by bunker spawn --server bunker-las-03 --ttl 20m, a successful bunker destroy, and bunker list returning to the pre-spawn count — the row's named acceptance: tasks.jsonl:145 foreman_note: 'Pre-spawn bunker list on las-03 had 0 agents. `bunker spawn --server bunker-las-03 --ttl 20m` returned agent dad5334f with port range 30200-30299 ... `bunker destroy dad5334f` succeeded; post-destroy las-03 list returned No agents found (baseline restored).' Live `bunker list --server bunker-las-03` -> 'No agents found.' (0 agents = pre-spawn count). events.jsonl:807 repeats 'spawn dad5334f ports 30200-30299 ... destroy OK; list restored'.
  ✓ The previously SKIPPED install leg ran on the spawned agent: the foreman_note records the clone result, ./install.sh rc=0, terminal-jail --version matching pyproject, the pidns-capability-probe and fs-isolation-probe verdicts, a jailed PID-ns inode differing from the host inode, and the destructive-command block (builtin-rm-rf-root) — mirroring the las-02 checklist in the row detail: tasks.jsonl:145 foreman_note records all named items: 'public clone rc=0 (4s, HEAD 7287ddd), ./install.sh rc=0 (1s), terminal-jail 1.3.0 (matches pyproject), pidns-capability-probe FULL (backend: bwrap), fs-isolation-probe FULL ..., host PID ns pid:[4026531836] differed from jailed pid ns pid:[4026532724], `terminal-jail rm -rf /` rc=126 COMMAND BLOCKED builtin-rm-rf-root'. Version match verified against pyproject.toml:7 version = "1.3.0"; checklist mirrors docs/dogfood/2026-09-18-integration.md:175-183 las-02 table; probes exist at scripts/pidns-capability-probe.py and scripts/fs-isolation-probe.py. The one las-02 item not re-verified (bwrap private /proc) is explicitly disclosed as a residual and is not among the criterion's named items. Corroborated by events.jsonl:807 tick-411 verification block. [resolution 0.06; ./install.sh]
All three criteria are satisfied: bunker-las-03 is live-verified ONLINE, the spawn/destroy cycle (agent dad5334f, ports 30200-30299, list restored to 0) is recorded in the row's foreman_note, and the previously SKIPPED install leg is recorded with every named las-02 checklist item including version 1.3.0 matching pyproject.toml.

## Summary

Judge Result: DF-TERMINAL-JAIL-19

Stage tier1: PASS
    ✓ lint: scanners: nice=nice -n 10
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: scanners: nice=nice -n 10

Stage tier2: PASS
  COMPLETE
  ✓ bunker status --server bunker-las-03 reports ONLINE — the row's stated gate for dispatching the install leg: Live re-run: `bunker status --server bunker-las-03` -> 'Version: 0.1.4 / Status: ONLINE', rc=0. foreman_note in .coding-hermes/board/tasks.jsonl:145 records 'bunker status --server bunker-las-03 reported ONLINE (v0.1.4)'; corroborated by .coding-hermes/board/events.jsonl:807 (tick 411) bunker_las03='ONLINE v0.1.4'.
  ✓ A spawn-and-destroy cycle on bunker-las-03 succeeded: the row's foreman_note records the agent id and port range returned by bunker spawn --server bunker-las-03 --ttl 20m, a successful bunker destroy, and bunker list returning to the pre-spawn count — the row's named acceptance: tasks.jsonl:145 foreman_note: 'Pre-spawn bunker list on las-03 had 0 agents. `bunker spawn --server bunker-las-03 --ttl 20m` returned agent dad5334f with port range 30200-30299 ... `bunker destroy dad5334f` succeeded; post-destroy las-03 list returned No agents found (baseline restored).' Live `bunker list --server bunker-las-03` -> 'No agents found.' (0 agents = pre-spawn count). events.jsonl:807 repeats 'spawn dad5334f ports 30200-30299 ... destroy OK; list restored'.
  ✓ The previously SKIPPED install leg ran on the spawned agent: the foreman_note records the clone result, ./install.sh rc=0, terminal-jail --version matching pyproject, the pidns-capability-probe and fs-isolation-probe verdicts, a jailed PID-ns inode differing from the host inode, and the destructive-command block (builtin-rm-rf-root) — mirroring the las-02 checklist in the row detail: tasks.jsonl:145 foreman_note records all named items: 'public clone rc=0 (4s, HEAD 7287ddd), ./install.sh rc=0 (1s), terminal-jail 1.3.0 (matches pyproject), pidns-capability-probe FULL (backend: bwrap), fs-isolation-probe FULL ..., host PID ns pid:[4026531836] differed from jailed pid ns pid:[4026532724], `terminal-jail rm -rf /` rc=126 COMMAND BLOCKED builtin-rm-rf-root'. Version match verified against pyproject.toml:7 version = "1.3.0"; checklist mirrors docs/dogfood/2026-09-18-integration.md:175-183 las-02 table; probes exist at scripts/pidns-capability-probe.py and scripts/fs-isolation-probe.py. The one las-02 item not re-verified (bwrap private /proc) is explicitly disclosed as a residual and is not among the criterion's named items. Corroborated by events.jsonl:807 tick-411 verification block. [resolution 0.06; ./install.sh]
All three criteria are satisfied: bunker-las-03 is live-verified ONLINE, the spawn/destroy cycle (agent dad5334f, ports 30200-30299, list restored to 0) is recorded in the row's foreman_note, and the previously SKIPPED install leg is recorded with every named las-02 checklist item including version 1.3.0 matching pyproject.toml.

Overall: PASS ✓
