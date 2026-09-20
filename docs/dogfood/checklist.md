# Terminal Jail — Dogfood Checklist

*Standing items to run before declaring an egress/rule workstream closed.
Started 2026-09-20 (DF-TERMINAL-JAIL-31); add items as dogfood runs expose
gaps the engine-level verdicts alone did not catch.*

- When a closure claims a rule CLASS is covered, probe at least one shape
  the rule deliberately does not target (scoped source, different client,
  quoted form) before closing.
