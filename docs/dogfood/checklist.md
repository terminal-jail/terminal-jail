# Terminal Jail — Dogfood Checklist

*Standing items to run before declaring an egress/rule workstream closed.
Started 2026-09-20 (DF-TERMINAL-JAIL-31); add items as dogfood runs expose
gaps the engine-level verdicts alone did not catch.*

- When a closure claims a rule CLASS is covered, probe at least one shape
  the rule deliberately does not target (scoped source, different client,
  quoted form) before closing.
- Scratch HOMEs and scratch trees under `/tmp/dogfood-*` must be created 0700
  and must never receive credential files; run
  `scripts/scratch-home-hygiene.sh` at the end of every dogfood tick and treat
  a non-zero exit as a blocker before closing the run.
