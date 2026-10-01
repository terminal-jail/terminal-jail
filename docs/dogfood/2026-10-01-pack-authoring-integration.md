docs/dogfood/2026-10-01-pack-authoring-integration.md — how to author a rule pack in practice as of 2026-10-01, and the friction to avoid.

## What was tested (angle)
The 2026-09-28 pack-authoring feature (7aadde8, schema subcommand + example pack + README §"Authoring a pack"). TJ-DF-034 (validated packs had no install path) and TJ-DF-035 (schema learnable only from source) both got fixes in that feature — this run was a REAL authoring pass over the result, not a repeat of prior fresh-install runs.

## The real loop that works
A pack author today:
1. Read the schema: `python3 scripts/rule-pack-tool.py schema` (or the commented example-pack.yaml).
2. Write a pack with ids in the derived namespace `pack-<name>-*` where <name> is your file's basename. THE RULE: id must be `pack-my-household-pack-*` for a file named `my-household-pack.yaml` — a descriptive-but-different id prefix is refused at review time AND at install time.
3. Validate BEFORE installing: `scripts/rule-pack-tool.py validate my-pack.yaml --pack-name my-pack`.
4. Install into a real or scratch home: `./install.sh --rule-pack-file ~/my-household-pack.yaml` (base install always completes; a refused/invalid pack is a loud skip + exit 2).
5. Drive real commands and inspect verdicts: `/bin/terminal-jail <cmd>` (wrapper) or the JSON bridge (echo a `{"command": ...}` JSON into the bridge script).
6. Iterate: `./install.sh --unrule-pack <packname> && ./install.sh --rule-pack-file ...` (this two-step dance is required every edit, currently).
7. Uninstall: `./install.sh --uninstall` clears the whole install (wrapper, lib tree, rules incl. installed pack) and your own file stays put somewhere else.

## Errors we hit and went around
- `match.type: regex` — refused; the correct spelling is `pattern` with a pattern field (TJ-DF-035 fix already covers this; the corrected spelling still caught out MY first attempt).
- Install refused, "id outside the pack namespace" — id prefix must match the file basename.
- A second install of an edited pack refuses with "already installed" telling you to --rule-pack + --unrule-pack first (user had to rediscover the dance themselves; nothing tells them the uninstall step is safe, only that the install was skipped; see TJ-DF-041 filed today).

## The one line a fresh author must not forget
`match.type` vocabulary is small (9 types). `regex` is allowed ONLY as the pattern field. The schema tool nails this, and example-pack.yaml says it in a comment — both fixes at 7aadde8 work.

## One perf number (not a row — not user-noticeable)
Warm `install.sh --rule-pack-file` redeploy, package-present base: 13.6 ms ± 1.0 ms (10-run hyperfine). Cold install that also creates the rules dir: 0.032 s / 0.03 s. Nothing here is slow enough to bother a user.

## What was left in this file
A pointer to fresh-machine fresh-user behavior (including the PyYAML trap) → TJ-DF-040 filed 2026-10-01; see the dogfood log entry names it as this run's finding.
