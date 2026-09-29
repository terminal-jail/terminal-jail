# Dogfood Record — 2026-09-29 — Hermes plugin refresh (REVIEW-TJ-005)

## What and why

The live Hermes observability plugin at `~/.hermes/plugins/terminal-jail/`
was stale: `plugin.yaml` reported **0.2.0** (installed 2026-09-18), while
the repo checkout ships **1.2.0**. The containment layer
(`~/.local/bin/terminal-jail`, `~/.local/lib/terminal-jail`) was already
current (drift=0 vs engine per the REVIEW-TJ-005 brief); only the plugin
lagged. Task: reinstall the plugin from the current checkout and record it.

## Before state

```
$ grep version ~/.hermes/plugins/terminal-jail/plugin.yaml
version: "0.2.0"

$ stat -c '%y %n' ~/.hermes/plugins/terminal-jail/plugin.yaml
2026-09-18 16:19:56.093566750 -0500 ~/.hermes/plugins/terminal-jail/plugin.yaml
```

Repo-side truth: `plugin/plugin.yaml` → `version: "1.2.0"`.

## Command used

```
$ cd /home/kara/terminal-jail && ./install.sh --hermes-plugin
terminal-jail installer: detected architecture x86_64
terminal-jail installer: refreshed Hermes plugin tree in /home/kara/.hermes/plugins/terminal-jail (stale files removed)
terminal-jail installer: deployed Hermes plugin v1.2.0 to /home/kara/.hermes/plugins/terminal-jail
terminal-jail installer: enable it in ~/.hermes/config.yaml (plugins.enabled: terminal-jail) and restart Hermes — see docs/quickstart.md section 3d.
EXIT=0
```

## After state (verification)

```
$ grep version ~/.hermes/plugins/terminal-jail/plugin.yaml
version: "1.2.0"

$ stat -c '%y %n' ~/.hermes/plugins/terminal-jail/plugin.yaml \
                   ~/.hermes/plugins/terminal-jail/__init__.py
2026-09-29 17:33:07.068655846 -0500 ~/.hermes/plugins/terminal-jail/plugin.yaml
2026-09-29 17:33:07.059721754 -0500 ~/.hermes/plugins/terminal-jail/__init__.py

$ diff -r /home/kara/terminal-jail/plugin /home/kara/.hermes/plugins/terminal-jail \
    && echo DIFF-CLEAN
DIFF-CLEAN: installed tree == repo plugin/
```

The installer used its UPDATE semantics (TJ-DF-022): stale files removed,
then the current tree deployed. Full-tree diff against the repo's
`plugin/` is clean, so the installed payload — not just `plugin.yaml` —
matches 1.2.0 exactly (payload spot-check: `plugin.yaml` + `__init__.py`
mtimes all 2026-09-29 17:33; no pre-refresh files remain).

## Notes / follow-ups

- **Gateway restart recommended but NOT performed** (out of scope for
  REVIEW-TJ-005): the running Hermes gateway may still hold the 0.2.0
  module in memory until restarted. `plugins.enabled: terminal-jail` was
  already active, so a restart picks the refreshed tree up.
- Containment layer untouched (already current).
- No board files, `.gitreins/`, `scripts/`, or plugin source were modified.
