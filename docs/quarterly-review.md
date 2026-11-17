# Quarterly Review Checklist (T10.4)

Quarterly review of the terminal-jail plugin to ensure ongoing compatibility, security, and correctness.

## Review Schedule

- Q1 review: April 1
- Q2 review: July 1
- Q3 review: October 1
- Q4 review: January 1

## Pre-Review Setup

```bash
cd /home/kara/terminal-jail
git pull --rebase
python3 -m pip install -e ".[dev]" 2>/dev/null || true
```

## 1. Kernel Compatibility (5 min)

- [ ] Run `scripts/kernel-watchdog.sh` — check for regressions
- [ ] Run `scripts/unshare-tracker.sh` — confirm flag combinations still work
- [ ] Check `uname -r` against COMPATIBILITY.md — update if new kernel
- [ ] Review LKML monitoring notes from the quarter — any relevant kernel changes?
- [ ] Test on the latest Ubuntu LTS kernel available

## 2. Test Suite (10 min)

- [ ] `python3 -m pytest plugin/ -v --tb=short` — all tests pass or skip with reason
- [ ] `python3 -m pytest plugin/test_interruptor_integration.py -v` — integration tests pass (or skip on blocked kernel)
- [ ] `python3 -m pytest plugin/test_seccomp.py -v` — seccomp tests pass
- [ ] `python3 -m pytest plugin/test_plugin.py -v` — unit tests pass
- [ ] Record test counts: `passed=N, skipped=N, failed=0`

## 3. Standalone CLI (3 min)

Every line below is executed verbatim by `scripts/docs-check.py` in CI: the
first inline-code span of a line is its argv, it must exit 0, and the outcome
named after the dash is asserted (usage text, version string, printed marker),
so a line that stops working fails the build. The first non-flag argument IS
the command — the wrapper has no `--` end-of-options terminator, and the only
isolation flags are `--user` and `--seccomp` (they compose). A host that
cannot create the namespace refuses loudly (exit 2, `command not run`);
`docs-check.py` reports that line as SKIP with the reason, never as PASS.

- [ ] `./standalone/terminal-jail --help` — rc 0; usage names the isolation flags `--user` and `--seccomp`
- [ ] `./standalone/terminal-jail --version` — rc 0; prints `terminal-jail <version>`, equal to `pyproject.toml`
- [ ] `./standalone/terminal-jail echo hello` — rc 0; prints `hello` — the command runs inside the jail with its arguments passed through without shell re-parsing
- [ ] `./standalone/terminal-jail --user printenv TERMINAL_JAIL_FS_ISOLATION` — rc 0; prints `mapped` or `degraded`: the `--user` launch ran and states its own filesystem-isolation outcome (PID-namespace containment and identity env scrub are always part of it)
- [ ] `./standalone/terminal-jail --seccomp printenv TERMINAL_JAIL_SECCOMP` — rc 0; prints `1`: the launch went through the seccomp-loader handoff (without the flag the marker is absent and `printenv` exits 1)
- [ ] `./standalone/terminal-jail --user --seccomp echo hello` — rc 0; prints `hello`: the two isolation flags compose

## 4. Hermes Integration (5 min)

- [ ] Plugin loads: `hermes plugin list 2>/dev/null | grep terminal-jail` or check `plugin/__init__.py`
- [ ] Check plugin log for errors: `grep terminal.jail ~/.hermes/logs/agent.log | tail -5`
- [ ] Metrics export: `python3 scripts/metrics-export.py` — runs without error
- [ ] Verify `HERMES_TERMINAL_JAIL_USER_NS` env var handling (truthy/falsy)

## 5. Security Review (10 min)

- [ ] Review seccomp BPF filter — any new dangerous syscalls to add?
- [ ] Check AppArmor policy — any changes to `kernel.apparmor_restrict_unprivileged_userns`?
- [ ] Review threat model (`docs/threat-model.md`) — any new threats to add?
- [ ] Check dependency audit (`docs/dependency-audit.md`) — zero Python deps still true?
- [ ] Verify `.gitleaks.toml` — no new permissive allowlist patterns

## 6. Documentation (5 min)

- [ ] README.md — version and feature list current?
- [ ] COMPATIBILITY.md — kernel matrix up to date?
- [ ] CHANGELOG.md — all significant changes logged?
- [ ] CONTRIBUTING.md — process still accurate?
- [ ] Issue templates — still relevant?

## 7. CI/CD (3 min)

- [ ] GitHub Actions: `gh run list -R terminal-jail/terminal-jail --limit 5` — all green?
- [ ] Any CI configuration drift? (runner deprecation, action version bumps)
- [ ] `.github/workflows/ci.yml` — still correct test commands?

## 8. Community & Issues (5 min)

- [ ] GitHub Issues: `gh issue list -R terminal-jail/terminal-jail --limit 20` — any unanswered?
- [ ] Open PRs: `gh pr list -R terminal-jail/terminal-jail` — any pending review?
- [ ] PR SLA compliance (see `docs/pr-sla.md`) — within targets?
- [ ] Hermes core PR status — any movement on the `--sandbox` flag?

## 9. Roadmap (5 min)

- [ ] Review BLOCKED tasks on `.coding-hermes/tasks.md` — any unblocked this quarter?
- [ ] Any new kernel features that enable previously-blocked functionality?
- [ ] Any new Hermes core hooks that terminal-jail could use?
- [ ] Update DuckBrain with findings

## Review Sign-off

| Field | Value |
|-------|-------|
| Date | |
| Reviewer | |
| Kernel version | |
| Tests passed | |
| Tests skipped | |
| CI status | |
| New issues filed | |
| BLOCKED tasks unblocked? | |
| Actions required before next review | |

## Post-Review

- [ ] Commit review findings to git
- [ ] Update DuckBrain `/project/terminal-jail/status`
- [ ] File issues for any new gaps found
- [ ] Update `.coding-hermes/tasks.md` if new tasks created
