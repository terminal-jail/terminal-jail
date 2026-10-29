# Terminal-jail dogfood — rule-pack authoring and fresh install

Tick: terminal-jail-dogfood-2026-10-29-10-09-24
HEAD: fd2638563a65dfb2932b7e111eda1d49a18b9eb8

## Promise
A user can install terminal-jail from a checkout, author a custom rule pack from the documented schema, install/replace/remove it, and use the CLI on a fresh machine.

## Local user workflow
The isolated local install used `HOME=/tmp/df-tj-20261029-100924/home`, `TERMINAL_JAIL_INSTALL_DIR=/tmp/df-tj-20261029-100924/bin`, `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=/tmp/df-tj-20261029-100924/config/rules.d`, and `--no-path`. Base install returned rc=0 in 0.67s and reported v1.3.0, all three loaders, default rules, and Landlock ABI 8. `--list-rule-packs` returned rc=0 in 0.09s.

The documented authoring loop was followed through `scripts/rule-pack-tool.py schema` and a real external pack. The first literal pack used `match.type: command_prefix`; validation correctly returned rc=2 and named the accepted vocabulary. The installer still completed the base install but returned rc=2 and wrote no external pack. This is onboarding friction, not a runtime failure: the repository's longer authoring note gives the correction (`type: pattern` plus a pattern field), but the minimal schema path did not prevent the first invalid shape. Finding: TJ-DF-058.

The benchmark returned rc=0: cold start 4.31ms, warm start 4.060ms, 1KB parse 0.282ms, 500-rule evaluation 0.160ms. These are not user-noticeable; no performance row was filed.

Evidence transcripts are retained outside the repository at `/tmp/df-tj-20261029-100924/`.

## Fresh-machine install leg
The prescribed helper was run directly, not through a retired driver. `bunker-qa.sh launch` passed its fence check and spawned agent `dbccd074` on `bunker-las-03`, but the fresh-install sync stopped before product installation: `ssh: connect to host 100.69.3.13 port 2223: Connection refused`. The agent was destroyed explicitly, and a post-destroy `bunker list --server bunker-las-03 --status all` returned `No agents found`.

Verdict: `SKIPPED-install-bunker` for this tick. No fresh-machine product-install PASS is claimed. Finding TJ-DF-059 records the helper/transport defect separately from terminal-jail behavior. Evidence path: `/tmp/bunker-qa-evidence-20261029T1025-terminal-jail.jsonl`.

## Value judgment
The local installer and CLI are useful and fast enough for the measured operations. The custom-pack workflow is usable only if the author discovers the correction beyond the shortest schema path. Fresh-machine installability remains unverified because the install plane failed before clone/install.

## Findings
- TJ-DF-058 — external pack authoring needed source-level correction after the literal schema attempt.
- TJ-DF-059 — bunker fresh-install launch could not sync the spawned agent on the configured SSH port; teardown was verified.

## Follow-up verification — TJ-DF-058

The corrected copy-paste example was re-run from the repository checkout through the full local workflow. `scripts/rule-pack-tool.py validate` returned rc=0; `install.sh --no-path --rule-pack-file` returned rc=0 and wrote the derived pack; the installed bridge returned `action=block` with `rule_id=pack-my-pack-demo`; `--replace-rule-packs` changed both the installed file and the bridge verdict; and `--uninstall-rule-pack-file` removed the file and restored the example command to `action=allow`. The regression is permanently covered by `plugin/test_rule_packs.py::TestExternalPackSchemaExample::test_documented_external_pack_installs_replaces_and_uninstalls_end_to_end`.

Verification witnesses: targeted test 3 passed; plugin suite 1907 passed/12 skipped; ruff passed; GitReins Tier 1 passed. The tests use only temporary HOME, install, and rules directories, so the host installation was not modified by the regression.
