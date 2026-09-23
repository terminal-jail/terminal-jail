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
- [ ] `python3 -m pytest plugin/test_integration.py -v` — integration tests pass (or skip on blocked kernel)
- [ ] `python3 -m pytest plugin/test_seccomp.py -v` — seccomp tests pass
- [ ] `python3 -m pytest plugin/test_plugin.py -v` — unit tests pass
- [ ] Record test counts: `passed=N, skipped=N, failed=0`

## 3. Standalone CLI (3 min)

- [ ] `standalone/terminal-jail --help` — prints usage
- [ ] `standalone/terminal-jail --version` — prints correct version
- [ ] `standalone/terminal-jail -- echo hello` — wraps command correctly
- [ ] `standalone/terminal-jail --user --pid --fork -- echo hello` — user NS works
- [ ] `standalone/terminal-jail --seccomp -- echo hello` — seccomp filter applies

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
