# Pull Request & Issue SLA (T10.5)

Service Level Agreement for responding to issues and pull requests on the terminal-jail repository.

## Response Time Targets

| Type | First Response | Resolution / Merge |
|------|---------------|-------------------|
| **Critical bug** (security, data loss, crash) | 24 hours | 72 hours |
| **High-priority bug** (functional breakage) | 48 hours | 1 week |
| **Medium-priority bug** (non-critical) | 1 week | 2 weeks |
| **Low-priority bug** (cosmetic, edge case) | 2 weeks | Next quarterly review |
| **Feature request** | 1 week | Triage only — no guarantee |
| **Documentation PR** | 3 days | 1 week |
| **Code PR (small)** | 3 days | 1 week |
| **Code PR (large)** | 1 week | 2 weeks |

## Triage Labels

Apply within 24 hours of issue/PR creation:

| Label | Meaning |
|-------|---------|
| `bug` | Confirmed defect |
| `enhancement` | Feature request |
| `documentation` | Docs-only change |
| `good first issue` | Suitable for new contributors |
| `help wanted` | Needs community contribution |
| `blocked` | Cannot proceed — external dependency |
| `wontfix` | Will not be addressed |

## Severity Classification

### Critical
- Security vulnerability in seccomp filter, user namespace isolation, or command wrapping
- Plugin crash that takes down the Hermes agent
- Kernel regression that breaks all functionality

### High
- Functional breakage (command wrapping fails, exit codes wrong)
- Test suite failure on supported kernels
- CI pipeline broken

### Medium
- Non-critical bug with workaround
- Documentation error
- Performance regression (non-blocking)

### Low
- Typo in docs
- Cosmetic issue
- Edge case affecting <1% of users

## Escalation Path

1. Issue filed → auto-labeled by template
2. Human triage within 24h (business days) → severity assigned
3. If no response within SLA window → escalate to @wojonstech
4. If still no response → Hermes core team can override

## Maintenance Windows

- **Regular:** Any time — low-risk changes merged anytime CI is green
- **Breaking changes:** Quarterly review windows only (April, July, October, January)
- **Security patches:** Immediately — bypass normal review process

## Staleness Policy

| Type | Stale after | Closed after stale |
|------|------------|-------------------|
| Bug (no repro) | 30 days | 60 days |
| Feature request (no activity) | 90 days | 180 days |
| PR (no review response) | 14 days | 30 days |
| PR (no author response) | 14 days | 30 days |

Stale issues/PRs get a `stale` label and a bot comment. If no activity after the stale period, they are closed with a `wontfix` or `stale` label.

## Metrics

Track quarterly:
- Average first response time
- Average resolution time
- SLA compliance percentage (per severity)
- Stale issue count
- Open PR age distribution

## Repository

- **GitHub:** https://github.com/terminal-jail/terminal-jail
- **Maintainer:** Alexis Okuwa (wojonstech@gmail.com)
- **Last updated:** 2026-07-21
