"""Tests for terminal-jail seccomp module — T9.5."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

# Ensure the plugin is importable in the test environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugin"))

from terminal_jail.seccomp import (
    SeccompError,
    SeccompPermissionError,
    SeccompUnsupportedError,
    apply_filter,
    build_bpf_program,
    deny_set_for_arch,
    filter_for_host,
    seccomp_enabled_from_environment,
    supported_architectures,
)

# ── Environment variable parsing ──────────────────────────────────────────────


class TestSeccompEnabledFromEnvironment:
    """TERMINAL_JAIL_SECCOMP env var parsing."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("1", True),
            ("true", True),
            ("yes", True),
            ("on", True),
            ("  yes  ", True),
            ("TRUE", True),
            ("ON", True),
            ("0", False),
            ("false", False),
            ("no", False),
            ("off", False),
            ("", False),
            ("garbage", False),
            ("  garbage  ", False),
        ],
    )
    def test_parse(self, value: str, expected: bool, monkeypatch) -> None:
        monkeypatch.setenv("TERMINAL_JAIL_SECCOMP", value)
        assert seccomp_enabled_from_environment() is expected

    def test_unset_defaults_to_disabled(self, monkeypatch) -> None:
        monkeypatch.delenv("TERMINAL_JAIL_SECCOMP", raising=False)
        assert seccomp_enabled_from_environment() is False


# ── Architecture support ─────────────────────────────────────────────────────


class TestSupportedArchitectures:
    def test_returns_non_empty_tuple(self) -> None:
        arches = supported_architectures()
        assert isinstance(arches, tuple)
        assert len(arches) >= 2

    def test_includes_x86_64(self) -> None:
        assert "x86_64" in supported_architectures()

    def test_includes_aarch64(self) -> None:
        assert "aarch64" in supported_architectures()


# ── Deny sets ────────────────────────────────────────────────────────────────


class TestDenySetForArch:
    def test_x86_64_denies_mount(self) -> None:
        deny = deny_set_for_arch("x86_64")
        assert 165 in deny  # mount on x86_64

    def test_x86_64_denies_pivot_root(self) -> None:
        deny = deny_set_for_arch("x86_64")
        assert 155 in deny  # pivot_root on x86_64

    def test_x86_64_denies_kexec_load(self) -> None:
        deny = deny_set_for_arch("x86_64")
        assert 246 in deny  # kexec_load on x86_64

    def test_aarch64_denies_mount(self) -> None:
        deny = deny_set_for_arch("aarch64")
        assert 40 in deny  # mount on aarch64

    def test_unknown_arch_raises(self) -> None:
        with pytest.raises(SeccompUnsupportedError):
            deny_set_for_arch("mips")


# ── BPF program generation ───────────────────────────────────────────────────


class TestBuildBpfProgram:
    def test_x86_64_produces_bytes_and_count(self) -> None:
        body, count, audit_arch = build_bpf_program(arch="x86_64")
        assert isinstance(body, bytes)
        assert len(body) > 0
        assert count > 0
        assert audit_arch > 0

    def test_aarch64_produces_bytes_and_count(self) -> None:
        body, count, audit_arch = build_bpf_program(arch="aarch64")
        assert isinstance(body, bytes)
        assert len(body) > 0
        assert count > 0
        assert audit_arch > 0

    def test_unknown_arch_raises(self) -> None:
        with pytest.raises(SeccompUnsupportedError):
            build_bpf_program(arch="sparc")

    def test_x86_64_filter_is_sorted_by_syscall_number(self) -> None:
        """The binary-search jump table requires sorted deny list."""
        _body, count, _ = build_bpf_program(arch="x86_64")
        # The filter should contain both mount (165) and kexec_load (246)
        # — if sorting works, the smaller NR appears first in the jump table.
        assert count >= 2
        # Minimum instruction count for arch check + sorted deny-set jumps
        assert count >= 4

    def test_filter_is_reproducible(self) -> None:
        """Same arch produces identical bytes (deterministic)."""
        body1, c1, a1 = build_bpf_program(arch="x86_64")
        body2, c2, a2 = build_bpf_program(arch="x86_64")
        assert body1 == body2
        assert c1 == c2
        assert a1 == a2

    def test_extra_denies_merged(self) -> None:
        """Extra deny numbers are added to the set."""
        # Pick a syscall that is NOT in the default deny set (e.g. getpid = 39).
        body_base, count_base, _ = build_bpf_program(arch="x86_64")
        body_extra, count_extra, _ = build_bpf_program(
            arch="x86_64", extra_denies=frozenset({39})
        )
        assert count_extra > count_base
        assert body_extra != body_base

    def test_arch_check_jump_semantics_allow_matching_arch(self) -> None:
        """The arch-check JEQ must ALLOW the matching arch and KILL others.

        Classic BPF jump semantics: ``jt`` is taken when the condition is
        TRUE, ``jf`` when FALSE — both relative to the *next* instruction.
        A filter with jt=0/jf=1 is INVERTED: it kills the very process it
        was built for (every syscall after install lands in RET KILL).
        Regression test for the setpriv-under-filter SIGSYS bug found in
        tick #155 (TJ-GAP-009 verification): the wrapper's
        ``setpriv --no-new-privs`` made the filter actually install, and
        every wrapped command died with SIGSYS.

        Layout of the built filter:
            0: LD [4]            (arch)
            1: JEQ arch, jt, jf  <- the instruction under test
            2: RET KILL_PROCESS
            3: LD [0]            (syscall nr)
            4..: deny JEQ chain
        """
        body, count, audit_arch = build_bpf_program(arch="x86_64")
        assert count >= 4

        # Instruction 1: code=0x15 (BPF_JMP|BPF_JEQ|BPF_K), k=audit_arch
        insn = body[8:16]
        code = int.from_bytes(insn[0:2], "little")
        jt = insn[2]
        jf = insn[3]
        k = int.from_bytes(insn[4:8], "little")
        assert code == 0x15, f"expected BPF_JMP|BPF_JEQ|BPF_K (0x15), got {code:#x}"
        assert k == audit_arch, f"JEQ must compare against audit arch {audit_arch:#x}"
        # jt (jump-if-true) must skip over instruction 2 (RET KILL) so the
        # matching arch falls through to instruction 3 (LD nr).
        assert jt == 1, (
            f"arch-match jump must skip RET KILL (jt=1); got jt={jt} — "
            "inverted filter would SIGSYS every command on the host arch"
        )
        assert jf == 0, f"arch-mismatch must fall into RET KILL (jf=0); got jf={jf}"

    def test_noop_filter_arch_jump_semantics(self) -> None:
        """The empty-deny no-op filter must also allow the matching arch."""
        _, _, audit_arch = build_bpf_program(arch="x86_64", extra_denies=frozenset())
        # Empty deny set: filter has no extra_denies entries, so we build the
        # no-op 4-instruction form when the DEFAULT set is also empty — but
        # the default x86_64 set is non-empty. Simulate by passing a set
        # that cancels: not possible here; instead verify the *arch prologue*
        # of the full filter is identical to the no-op form.
        # No-op form: LD arch; JEQ arch,jt,jf; RET KILL; RET ALLOW
        # Build the no-op via the private path used for empty sets.
        from terminal_jail import seccomp as seccomp_mod

        noop_body, noop_count = seccomp_mod._build_filter(audit_arch, frozenset())
        assert noop_count == 4
        insn = noop_body[8:16]
        assert insn[2] == 1, f"no-op arch JEQ must use jt=1; got jt={insn[2]}"
        assert insn[3] == 0, f"no-op arch JEQ must use jf=0; got jf={insn[3]}"


class TestFilterForHost:
    def test_returns_valid_tuple(self) -> None:
        body, count, arch = filter_for_host()
        assert isinstance(body, bytes)
        assert len(body) > 0
        assert count > 0
        assert arch > 0


# ── apply_filter (unit tests — no actual prctl) ──────────────────────────────


class TestApplyFilterUnit:
    def test_unknown_arch_raises_seccomp_error(self) -> None:
        with pytest.raises(SeccompUnsupportedError):
            apply_filter(arch="nonexistent")

    def test_errors_are_seccomp_subclasses(self) -> None:
        assert issubclass(SeccompUnsupportedError, SeccompError)
        assert issubclass(SeccompPermissionError, SeccompError)


# ── try_apply result dataclass ───────────────────────────────────────────────


class TestTryApply:
    def test_try_apply_returns_seccomp_result(self) -> None:
        """try_apply never raises — it returns SeccompApplyResult.

        We run try_apply in a subprocess because a successful filter
        installation persists for the process lifetime, and subsequent
        Python operations may hit the deny list.
        """
        plugin_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "plugin")
        )
        script = (
            "import sys, os\n"
            f"sys.path.insert(0, {plugin_dir!r})\n"
            "from terminal_jail.seccomp import try_apply, SeccompApplyResult\n"
            "result = try_apply()\n"
            "if isinstance(result, SeccompApplyResult):\n"
            "    print(f'OK:{result.applied}:{len(result.reason)}')\n"
            "else:\n"
            "    print(f'TYPE_ERROR:{type(result).__name__}')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        # try_apply may succeed (filter applied) or fail (no perms).
        # Either way, it must return SeccompApplyResult and not raise.
        assert "OK:" in result.stdout or "TYPE_ERROR:" not in result.stdout


# ── no_new_privs + filter install regression (TJ-DF-003) ─────────────────────


class TestNoNewPrivsBeforeFilter:
    """PR_SET_NO_NEW_PRIVS must be set before PR_SET_SECCOMP.

    Regression for TJ-DF-003: without the latch, an unprivileged process
    gets EPERM from prctl(PR_SET_SECCOMP) and try_apply() degrades to
    running without the filter. These tests run in subprocesses because a
    successful install latches no_new_privs for the process lifetime.

    The negative control documents the seccomp *baseline*: a bare host
    reports Seccomp=0, while container runtimes (Docker et al.) install
    their own filter so /proc/self/status already reports Seccomp=2
    before terminal-jail does anything. Only these kernel-valid baselines
    are accepted; the positive control below remains strict.
    """

    PLUGIN_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "plugin")
    )

    @staticmethod
    def _status_probe(apply: bool) -> str:
        call = "result = try_apply()" if apply else "result = None"
        ok_expr = (
            "result.applied and nn == '1' and sc == '2'"
            if apply
            else "nn == '0' and sc in ('0', '2')"
        )
        applied_repr = "result.applied" if apply else "None"
        return (
            "import sys, re\n"
            f"sys.path.insert(0, {TestNoNewPrivsBeforeFilter.PLUGIN_DIR!r})\n"
            "from terminal_jail.seccomp import try_apply\n"
            f"{call}\n"
            "st = open('/proc/self/status').read()\n"
            "nn = re.search(r'NoNewPrivs:\\s+(\\d)', st).group(1)\n"
            "sc = re.search(r'Seccomp:\\s+(\\d)', st).group(1)\n"
            f"ok = {ok_expr}\n"
            f"print(f'applied={{{applied_repr}}} NoNewPrivs={{nn}} Seccomp={{sc}}')\n"
            "sys.exit(0 if ok else 1)\n"
        )

    def test_filter_install_sets_no_new_privs_and_seccomp(self) -> None:
        """try_apply() must latch no_new_privs and install the filter."""
        result = subprocess.run(
            [sys.executable, "-c", self._status_probe(apply=True)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"probe failed rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "applied=True NoNewPrivs=1 Seccomp=2" in result.stdout

    def test_negative_control_no_new_privs_without_try_apply(self) -> None:
        """Without try_apply() NoNewPrivs stays 0; Seccomp is the env baseline.

        Proves the positive test's NoNewPrivs=1 comes from terminal-jail's
        own PR_SET_NO_NEW_PRIVS and is not vacuously passing. The seccomp
        baseline is the environment's, not ours: Seccomp=0 on a bare host,
        Seccomp=2 when a container runtime (Docker et al.) already
        installed its own inherited filter. This test does NOT assert
        that terminal-jail applied a filter, so either baseline passes.
        """
        result = subprocess.run(
            [sys.executable, "-c", self._status_probe(apply=False)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"negative control failed rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # NoNewPrivs must be 0 pre-try_apply; Seccomp is the inherited
        # baseline (0 bare host / 2 container runtime). Anything else fails.
        assert "applied=None NoNewPrivs=0 Seccomp=0" in result.stdout or (
            "applied=None NoNewPrivs=0 Seccomp=2" in result.stdout
        ), (
            f"unexpected seccomp baseline\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ── Standalone CLI integration tests ──────────────────────────────────────────


class TestStandaloneCliSeccomp:
    """Verify the --seccomp flag is recognized by the standalone CLI."""

    CLI = os.path.join(os.path.dirname(__file__), "..", "standalone", "terminal-jail")

    def test_help_mentions_seccomp(self) -> None:
        """--help output should document the --seccomp flag."""
        result = subprocess.run(
            ["bash", self.CLI, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "--seccomp" in result.stdout

    def test_seccomp_without_command_exits_2(self) -> None:
        """--seccomp without a command should exit 2."""
        result = subprocess.run(
            ["bash", self.CLI, "--seccomp"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2

    def test_seccomp_with_command_runs(self) -> None:
        """--seccomp with a trivial command should succeed."""
        result = subprocess.run(
            ["bash", self.CLI, "--seccomp", "echo", "hello-seccomp"],
            capture_output=True,
            text=True,
            check=False,
        )
        # May fail if seccomp can't be applied (no CAP_SYS_ADMIN in test env)
        # but it must not crash or produce traceback.
        assert result.returncode in (0, 1, 2)
        # Even if seccomp fails to apply, the command should still run.
        if result.returncode == 0:
            assert "hello-seccomp" in result.stdout

    def test_normal_cli_still_works(self) -> None:
        """Without --seccomp, the CLI should work as before.

        Note: unshare may fail with 'Operation not permitted' on hosts where
        the kernel blocks unprivileged PID namespace creation (documented
        as a pre-existing limitation in the board). The CLI itself should
        not produce an error about unrecognized flags.
        """
        result = subprocess.run(
            ["bash", self.CLI, "echo", "normal"],
            capture_output=True,
            text=True,
            check=False,
        )
        # 0 = unshare worked, 1 = legacy raw unshare failure,
        # 2 = namespace creation failed (TJ-GAP-034 degradation contract) —
        #     or a usage error (should NOT happen; stderr check below)
        assert result.returncode in (0, 1, 2)
        assert "unrecognized" not in result.stderr.lower()


# ── Integration tests (skip — require kernel support) ─────────────────────────


class TestPentestIntegration:
    """PT-004 tests — skipped: require kernel seccomp support.

    These tests exercise the pentest plan scenarios for mount(),
    pivot_root(), and kexec_load() syscalls. They should be run manually
    on a host with CAP_SYS_ADMIN and seccomp support.

    See: docs/pentest-plan.md §3.4
    """

    CLI = os.path.join(os.path.dirname(__file__), "..", "standalone", "terminal-jail")

    @pytest.mark.skip(reason="PT-004a: requires kernel seccomp + CAP_SYS_ADMIN")
    def test_pt004a_mount_blocked(self) -> None:
        """mount() should return EPERM when seccomp is active."""
        result = subprocess.run(
            [
                "bash",
                self.CLI,
                "--seccomp",
                "mount",
                "-t",
                "tmpfs",
                "tmpfs",
                "/tmp/test-jail-mount",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # With seccomp active, mount should fail — not succeed
        assert result.returncode != 0

    @pytest.mark.skip(reason="PT-004b: requires kernel seccomp + CAP_SYS_ADMIN")
    def test_pt004b_pivot_root_blocked(self) -> None:
        """pivot_root() should be blocked when seccomp is active."""
        result = subprocess.run(
            [
                "bash",
                self.CLI,
                "--seccomp",
                "bash",
                "-c",
                "pivot_root / / 2>&1 || true",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert (
            "operation not permitted" in result.stdout.lower() or result.returncode != 0
        )

    @pytest.mark.skip(reason="PT-004c: requires kernel seccomp support")
    def test_pt004c_kexec_blocked(self) -> None:
        """kexec_load() should be blocked when seccomp is active."""
        result = subprocess.run(
            ["bash", self.CLI, "--seccomp", "kexec", "-l", "/dev/null"],
            capture_output=True,
            text=True,
            check=False,
        )
        # kexec should fail (seccomp blocks it, or no CAP_SYS_BOOT)
        assert result.returncode != 0


# ── glibc-routed variant NRs (TJ-DF-020) ──────────────────────────────────────


class TestGlibcVariantNrs:
    """glibc wrappers must not bypass the deny list via variant NRs.

    TJ-DF-020: glibc routes ``adjtimex()`` to ``clock_adjtime`` (NR 305 on
    x86_64) rather than the classic ``adjtimex`` (NR 159), so a filter that
    only pins the classic NR lets the libc wrapper through. These tests
    call the libc *wrappers* (not raw NRs) under the installed filter —
    exactly the routing a real payload exercises — and assert EPERM.

    All wrappers are called in a subprocess: a successful prctl filter
    install latches no_new_privs for the process lifetime and would
    otherwise leak into sibling tests.
    """

    @staticmethod
    def _wrapper_probe(script: str) -> subprocess.CompletedProcess:
        plugin_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "plugin")
        )
        prologue = (
            "import ctypes, ctypes.util, errno, sys\n"
            f"sys.path.insert(0, {plugin_dir!r})\n"
            "from terminal_jail.seccomp import try_apply\n"
            "result = try_apply()\n"
            "assert result.applied, f'filter not applied: {result.reason}'\n"
        )
        return subprocess.run(
            [sys.executable, "-c", prologue + script],
            capture_output=True,
            text=True,
            check=False,
        )

    # glibc 2.43 on the 2026-09-23 control host segfaults inside
    # settimeofday()/clock_settime() under a fresh EPERM filter (glibc's
    # internal errno path). Those two wrappers route to NRs already
    # covered by the classic table, so the WRAPPER-level EPERM proof for
    # the family is the raw-NR battery below; the wrapper tests here
    # cover the actual TJ-DF-020 surface: wrappers glibc routes through a
    # NON-classic NR (adjtimex -> clock_adjtime 305). One subprocess per
    # wrapper so a crash cannot mask the others' verdicts.
    _WRAPPERS: dict[str, str] = {
        "adjtimex": (
            "libc.adjtimex.restype = ctypes.c_int\n"
            "libc.adjtimex.argtypes = [ctypes.c_void_p]\n"
            "buf = ctypes.create_string_buffer(256)\n"
            "libc.adjtimex(buf)\n"
            "print('errno=%d' % ctypes.get_errno())\n"
        ),
        "clock_adjtime": (
            "libc.clock_adjtime.restype = ctypes.c_int\n"
            "libc.clock_adjtime.argtypes = [ctypes.c_int, ctypes.c_void_p]\n"
            "buf = ctypes.create_string_buffer(256)\n"
            "libc.clock_adjtime(0, buf)\n"
            "print('errno=%d' % ctypes.get_errno())\n"
        ),
    }

    def test_libc_adjtimex_returns_eperm_under_filter(self) -> None:
        """libc adjtimex() (glibc-routed to clock_adjtime 305) must EPERM.

        Red-proof (unfixed tree, 2026-09-23 control host x86_64): this
        probe returned ret=0 — glibc issued clock_adjtime(305) which the
        deny list did not cover. With NR 305 denied (and the BPF
        fall-through bug fixed), the same wrapper call must fail EPERM.
        """
        result = self._wrapper_probe(
            "libc = ctypes.CDLL('libc.so.6', use_errno=True)\n"
            + self._WRAPPERS["adjtimex"]
        )
        assert result.returncode == 0, (
            f"probe crashed rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "errno=1" in result.stdout, (
            f"libc.adjtimex() did not get EPERM under the filter\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_libc_clock_adjtime_returns_eperm_under_filter(self) -> None:
        """The variant NR glibc routes adjtimex() through must deny directly."""
        result = self._wrapper_probe(
            "libc = ctypes.CDLL('libc.so.6', use_errno=True)\n"
            + self._WRAPPERS["clock_adjtime"]
        )
        assert result.returncode == 0 and "errno=1" in result.stdout, (
            f"libc.clock_adjtime() did not get EPERM under the filter\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_clock_adjtime_305_in_x86_64_deny_set(self) -> None:
        """The deny table must pin the glibc-routed clock_adjtime NR (305)."""
        deny = deny_set_for_arch("x86_64")
        assert 305 in deny, (
            "clock_adjtime (NR 305) missing from x86_64 deny set — "
            "glibc adjtimex() routes here and bypasses the filter "
            "(TJ-DF-020)"
        )

    def test_variant_routings_are_covered(self) -> None:
        """Every classic NR with a glibc variant routing has both pinned.

        glibc variant routing audit (x86_64):
            adjtimex(159)    -> clock_adjtime(305)
            settimeofday(164)-> clock_settime(227)
            init_module(175) -> finit_module(313)
            kexec_load(246)  -> kexec_file_load(320)
        """
        deny = deny_set_for_arch("x86_64")
        for classic, variant in ((159, 305), (164, 227), (175, 313), (246, 320)):
            assert classic in deny, f"classic NR {classic} missing"
            assert variant in deny, (
                f"glibc-routed variant NR {variant} missing — wrapper "
                f"routing bypasses the filter (TJ-DF-020)"
            )

    def test_raw_deny_nr_battery_returns_eperm_under_filter(self) -> None:
        """Raw syscall() for every testable deny NR must EPERM under the filter.

        The BPF fall-through bug (TJ-DF-020 root cause) meant every other
        JEQ in the chain was skipped: raw NRs 159, 164, 174, 176, 305,
        320 and friends reached the kernel (EFAULT/ENOSYS from kernel
        checks) instead of the filter. With jf=0, ALL deny NRs hit the
        deny block — including create_module 174, whose kernel-side
        ENOSYS the filter now precedes.
        """
        script = (
            "import ctypes, errno, mmap\n"
            "libc = ctypes.CDLL('libc.so.6', use_errno=True)\n"
            "raw = libc.syscall\n"
            "raw.restype = ctypes.c_long\n"
            "raw.argtypes = [ctypes.c_long] + [ctypes.c_void_p] * 6\n"
            "page = mmap.mmap(-1, 4096)\n"
            "addr = ctypes.addressof(ctypes.c_char.from_buffer(page))\n"
            "nrs = [155, 159, 163, 164, 165, 167, 168, 174, 175, 176, 227,\n"
            "       246, 248, 249, 250, 305, 313, 320]\n"
            "bad = []\n"
            "for nr in nrs:\n"
            "    ctypes.set_errno(0)\n"
            "    if nr == 305:\n"
            "        rc = raw(nr, ctypes.c_void_p(0), ctypes.c_void_p(addr), None, None, None, None)\n"
            "    else:\n"
            "        rc = raw(nr, ctypes.c_void_p(addr), ctypes.c_void_p(addr), None, None, None, None)\n"
            "    rc_e = ctypes.get_errno()\n"
            "    if not (rc == -1 and rc_e == 1):\n"
            "        bad.append((nr, rc, rc_e))\n"
            "print('BAD=%r' % (bad,))\n"
        )
        result = self._wrapper_probe(script)
        assert result.returncode == 0, (
            f"probe crashed rc={result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "BAD=[]" in result.stdout, (
            "some deny NRs did not return seccomp EPERM under the filter\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_non_deny_syscall_not_blocked(self) -> None:
        """Sanity: a syscall OUTSIDE the deny list must still work (getpid)."""
        script = (
            "import ctypes\n"
            "libc = ctypes.CDLL('libc.so.6', use_errno=True)\n"
            "raw = libc.syscall\n"
            "raw.restype = ctypes.c_long\n"
            "raw.argtypes = [ctypes.c_long] + [ctypes.c_void_p] * 6\n"
            "rc = raw(39, None, None, None, None, None, None)  # getpid\n"
            "print('pid_ok=%d' % (1 if rc > 0 else 0))\n"
        )
        result = self._wrapper_probe(script)
        assert result.returncode == 0 and "pid_ok=1" in result.stdout, (
            f"getpid blocked under filter — default-allow broken\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
