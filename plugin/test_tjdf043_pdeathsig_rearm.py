"""TJ-DF-043 — the mapped launch must survive its own cred changes.

Root cause (measured on Debian 13.7 / kernel 6.12.107, util-linux 2.41.5,
LD_PRELOAD syscall-order shim + per-shape teardown traces): util-linux's
uid-mapped launch runs ``prctl(PR_SET_PDEATHSIG)`` (``--kill-child=SIGKILL``)
in the forked child BEFORE the ``setgroups``/``setgid(-G)``/``setuid(-S)``
that the ``-S``/``-G`` flags request. The kernel clears the parent-death
setting on any thread-credential change (``commit_creds()``:
``task->pdeath_signal = 0`` when euid/egid/fsuid/fsgid change — man 2 prctl,
PR_SET_PDEATHSIG "cleared upon changes to any of the following thread
credentials"), so by the time the payload is exec'ed the ONLY teardown
linkage the mapped launch has is namespace-exit — and the payload is
namespace PID 1, which the kernel does not kill. The launcher's SIGKILL
leaves a real orphan (host uid = the subordinate uid, ppuid 1).

This is NOT a kernel-version divergence: the clear site (kernel/cred.c
commit_creds) and the delivery site (kernel/exit.c forget_original_parent)
are byte-identical between v6.12 and v7.0, and both Debian hosts orphan
while the dev host never exercises the mapped launch at all (AppArmor
denies setuid/setgroups inside unprivileged user namespaces, so the mapped
probe fails and the wrapper falls back mapping-less — a shape whose
parent keeps the caller's kuid, passes kill_ok_by_cred by uid equality,
and tears down). The failing kernel differed only in reaching the bug.

The fix (both launch sites, byte-parity pinned here): the mapped flags end
with a ``setpriv --pdeathsig=SIGKILL`` exec tail, so the process that
execs the payload RE-ARMS the parent-death signal AFTER the credential
changes that cleared it. setpriv --pdeathsig arms prctl(PR_SET_PDEATHSIG)
in its own process right before execve, preserving argv (exec tail) and
requiring no new dependency beyond util-linux itself (measured on the
failing kernel: mapped orphan -> teardown in 20 ms with the tail).
"""

from __future__ import annotations

import re

from terminal_jail.interruptor import userns

# The re-arm tail every mapped launch must end with (single source of truth:
# userns.py assembles the flags string; the wrapper must mirror it).
_PDEATHSIG_TAIL = re.compile(r"setpriv --pdeathsig=(?:SIGKILL|KILL)\b")


def test_mapped_flags_end_with_the_pdeathsig_rearm_tail() -> None:
    """The mapped template re-arms PDEATHSIG after its own -S/-G cred change.

    RED before the fix: the template ended at --kill-child=SIGKILL, so the
    only teardown linkage was armed before the cred changes that clear it.
    """
    flags = userns.mapped_user_flags()
    assert _PDEATHSIG_TAIL.search(flags), (
        f"mapped launch flags do not re-arm the parent-death signal after "
        f"the -S/-G credential change: {flags!r}"
    )


def test_mapped_flags_keep_the_kill_child_contract() -> None:
    """The re-arm tail is additive: --kill-child=SIGKILL stays armed for
    pre-exec deaths and hosts whose setpriv lacks --pdeathsig (the probe
    then fails and the launch falls back mapping-less, loudly)."""
    flags = userns.mapped_user_flags()
    assert "--kill-child=SIGKILL" in flags
    assert "--pid --fork" in flags
    assert "-S 65534" in flags and "-G 65534" in flags


def test_legacy_flags_unchanged() -> None:
    """The mapping-less launch keeps its exact shape: its parent keeps the
    caller's kuid (kill_ok_by_cred passes by uid equality), so it never had
    the cleared-signal defect."""
    assert userns.LEGACY_USER_FLAGS == "--user --pid --fork --kill-child=SIGKILL"
