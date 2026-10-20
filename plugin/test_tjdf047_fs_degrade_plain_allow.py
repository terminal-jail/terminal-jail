"""TJ-DF-047 — the plain-allow fs tier attach decision is never SILENT.

The board row's residual gap after TJ-DF-046 (7971495): the egress tier got a
loud attach decision on the plain-allow path, but the FILESYSTEM tier's own
gate still fell through silently on every non-rewritten exec. The modify path
cannot be silent (the loader execs inside the launch and prints its own
``WARNING: Landlock filesystem tier not applied (...)`` line), but the
plain-allow bwrap/unshare arms run this wrapper's gate BEFORE any loader:

* ``[ -f "$LANDLOCK_LOADER" ]`` false → the wrap is skipped with no line at
  all (a missing/renamed/overridden loader file);
* the TJ-DF-019 readability preflight false → the wrap is skipped with no
  line at all (the payload-uid cannot read the loader — the CI-shaped install
  with HOME at 0700/0750, the exact shape the board row names).

Either way the payload ran with NO kernel filesystem enforcement and NO
warning: the user only learns their containment ceiling from a composed-mode
inspection. This suite pins the fix — both plain-allow arms print the
loader's own warning wording, with a named cause, BEFORE the payload runs:

    terminal-jail: WARNING: Landlock filesystem tier not applied (<cause>);
    commands run unchanged without kernel filesystem enforcement — ...

while the modify path (criterion 3) stays byte-identical: the TJ-DF-046
egress seam is untouched (same counts this repo's other suites pin), the
loader's own two warning messages are untouched, and the mapped-launch skip
gains no line (a uid mapping IS filesystem isolation — a substitution, not a
degradation; the wrapper keys the gate on ``!= "mapped"`` and never on
``== "mapped"``, so the mapped branch has no degradation arm to print).

Structure mirrors test_tjdf046_egress_allow_path.py / the TJ-DF-047 contract
suite: PATH-stub launcher cells that are host-independent, a mapped-arm cell
probe-gated with an honest skip (this suite's author host denies setuid in
unprivileged user namespaces — the CI-shaped Ubuntu runner permits it), and
static wiring pins.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "standalone" / "terminal-jail"
FS_LOADER = PROJECT_ROOT / "standalone" / "landlock-loader.py"
RULES_MIRROR_DIR = PROJECT_ROOT / "plugin" / "terminal_jail" / "rules"

pytestmark = pytest.mark.standalone_cli

DEGRADE_PREFIX = "WARNING: Landlock filesystem tier not applied"
DEGRADE_FULL = (
    "WARNING: Landlock filesystem tier not applied ($1); commands run "
    "unchanged without kernel filesystem enforcement"
)


# ── Shared harness (same shape as test_tjdf046_egress_allow_path) ────────────

# Curated PATH stubs for the launchers: each records its full argv and EXECUTES
# the payload it was asked to run, so the wrapper's real dispatch — backend
# probe, tier attach decisions, trampoline — runs end to end without a kernel
# namespace. Unlike the DF-046 stub (whose naive "skip until the first
# non-option token" happens to fit unshare's flag grammar), the bwrap grammar
# needs ARITY: `--bind / /` carries two operand tokens, `--proc /proc` one, so
# a naive skip lands the payload boundary inside the flags and the wrapper's
# backend probe fails (measured: rc=2, "bwrap namespace creation failed").
_UNSHARE_STUB = """#!/usr/bin/env bash
log="${TJ_DF047_FS_STUB_LOG:?}"
for a in "$@"; do printf '%s\\0' "$a" >> "$log"; done
printf 'EOR\\0' >> "$log"
args=("$@")
i=0
while [ "$i" -lt "${#args[@]}" ]; do
    case "${args[$i]}" in
        -S|-G|-N|-M|-U|-r) i=$((i + 2)) ;;          # 1-arity unshare options
        -*) i=$((i + 1)) ;;                          # --word / --word=value
        *) break ;;                                  # first non-option: payload
    esac
done
exec "${args[@]:$i}"
"""

_BWRAP_STUB = """#!/usr/bin/env bash
log="${TJ_DF047_FS_STUB_LOG:?}"
for a in "$@"; do printf '%s\\0' "$a" >> "$log"; done
printf 'EOR\\0' >> "$log"
args=("$@")
i=0
while [ "$i" -lt "${#args[@]}" ]; do
    case "${args[$i]}" in
        --) i=$((i + 1)); break ;;                   # option/payload separator
        --bind|--dev-bind|--ro-bind|--file|--args) i=$((i + 3)) ;;
        --proc|--dev|--tmpfs|--dir|--perms) i=$((i + 2)) ;;
        -*) i=$((i + 1)) ;;                          # 0-arity flags
        *) break ;;
    esac
done
exec "${args[@]:$i}"
"""


def _base_env() -> dict[str, str]:
    """No ambient TERMINAL_JAIL_* leakage; rules pinned to the shipped mirror.

    TERMINAL_JAIL_LANDLOCK_NET stays UNSET: the egress knob is opt-in, so the
    net tier is silent in these cells by its own design and every tier line in
    an asserted stderr is the filesystem tier's.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env["TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR"] = str(RULES_MIRROR_DIR)
    env["TERMINAL_JAIL_INTERRUPTOR_RULES_DIR"] = str(RULES_MIRROR_DIR)
    return env


def _stub_launcher_path(tmp_path: Path) -> str:
    bindir = tmp_path / "stub-bin"
    bindir.mkdir(exist_ok=True)
    for name, body in (("unshare", _UNSHARE_STUB), ("bwrap", _BWRAP_STUB)):
        stub = bindir / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _run_cli(*args: str, env: dict[str, str], timeout: int = 60):
    return subprocess.run(
        [str(CLI_SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


# ── Wiring: the wrapper owns one fs degrade line, the DF-046 seam is intact ──


class TestFsDegradeWiring:
    def test_wrapper_owns_one_fs_degrade_line_naming_the_cause(self) -> None:
        """One helper, two plain-allow call sites (bwrap + unshare). The
        modify path gets its warnings from the loaders themselves and gains
        NO third call site."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count("_tj_fs_degrade() {") == 1, (
            "ONE helper definition — no per-arm copies"
        )
        assert text.count('_tj_fs_degrade "') == 4, (
            "exactly four calls: not-found + cannot-read, on bwrap AND unshare; "
            "the modify path gains no call site"
        )
        body_start = text.index("_tj_fs_degrade() {")
        body = text[body_start : text.index("}", body_start)]
        assert DEGRADE_FULL in body, (
            "the fs degrade must name the cause from its argument, "
            "in the loader's own wording"
        )
        assert "TERMINAL_JAIL_LANDLOCK=0" in body, (
            "the line must carry the deliberate opt-out, like the loader's"
        )

    def test_df046_egress_seam_is_untouched(self) -> None:
        """Criterion 3, wrapper side: the egress attach decision keeps its
        exact shape (the counts the DF-046/DF-047 suites already pin)."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count("_tj_egress_tier_decide") == 7
        assert text.count('!= "mapped"') == 4
        assert text.count('if [ "$TJ_LANDLOCK_ON" -eq 1 ]') == 3
        assert text.count("Landlock network (egress) tier not applied") == 1

    def test_modify_path_loader_warnings_are_untouched(self) -> None:
        """Criterion 3, loader side: the loader keeps both of its own warning
        messages — the modify path's degrade ladder prints through them and
        must not change."""
        loader_text = FS_LOADER.read_text(encoding="utf-8")
        assert loader_text.count(DEGRADE_PREFIX) == 2
        assert "tier module not found next to the loader" in loader_text
        assert "classify the host with" in loader_text

    def test_modify_branch_gains_no_degrade_call(self) -> None:
        start = text_start = CLI_SCRIPT.read_text(encoding="utf-8").index(
            'elif [ "$MODIFIED" -eq 1 ]'
        )
        end = text_start + CLI_SCRIPT.read_text(encoding="utf-8")[start:].index(
            'exec bash -c "$CMD_STR"'
        )
        modify_branch = CLI_SCRIPT.read_text(encoding="utf-8")[start:end]
        assert "_tj_fs_degrade" not in modify_branch
        assert "_tj_egress_degrade" not in modify_branch

    def test_mapped_launch_skip_has_no_degradation_arm(self) -> None:
        """A uid-mapped launch IS filesystem isolation — the fs tier's skip
        there is a substitution, not a degradation. Structural pin: the
        wrapper never keys anything on ``== "mapped"`` (bash equality is
        ``=``), so the mapped branch has no arm that could print; the
        probe-gated mapped-arm cell below covers the behavior end to end on a
        host that promotes the mapping."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count('== "mapped"') == 0

    def test_plain_gates_degrade_only_on_refusal_not_on_mapping(self) -> None:
        """Each plain-allow gate prints exactly the two named-cause refusals
        (not-found, cannot-read) and keeps the mapped check as a silent
        nested branch ahead of the readability probe."""
        text = CLI_SCRIPT.read_text(encoding="utf-8")
        assert text.count('_tj_fs_degrade "landlock-loader.py not found') == 2, (
            "one not-found cause per plain-allow arm (bwrap + unshare)"
        )
        assert (
            text.count('_tj_fs_degrade "the payload cannot read ${LANDLOCK_LOADER}')
            == 2
        ), "one cannot-read cause per plain-allow arm (bwrap + unshare)"
        for arm_anchor in (
            "proc_view=private (bwrap backend",
            "proc_view=host (unshare backend",
        ):
            arm = text[text.index(arm_anchor) :]
            mapped_pos = arm.index('!= "mapped"')
            after_mapped = arm[mapped_pos : mapped_pos + 600]
            probe_pos = after_mapped.index("test -r")
            between = after_mapped[:probe_pos]
            assert "_tj_fs_degrade" not in between, (
                f"{arm_anchor[:20]}: nothing may print on the mapped branch"
            )


# ── Launch shape: the degrade fires through the wrapper's real dispatch ──────


class TestFsDegradePlainAllow:
    def _run(self, tmp_path: Path, *payload: str, **knobs: str):
        env = _base_env()
        env.update(
            {
                "PATH": _stub_launcher_path(tmp_path),
                "HOME": str(tmp_path / "home"),
                "TJ_DF047_FS_STUB_LOG": str(tmp_path / "stub.log"),
                "TERMINAL_JAIL_JAIL_BACKEND": "unshare",
            }
        )
        (tmp_path / "home").mkdir(exist_ok=True)
        env.update(knobs)
        return _run_cli(*payload, env=env)

    def test_missing_fs_loader_degrades_on_the_unshare_plain_allow(
        self, tmp_path: Path
    ) -> None:
        result = self._run(
            tmp_path,
            "echo",
            "DF047-FS-OK",
            TERMINAL_JAIL_LANDLOCK_LOADER=str(tmp_path / "absent-loader.py"),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-OK" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr
        assert "not found" in result.stderr, result.stderr

    def test_unreadable_fs_loader_degrades_on_the_unshare_plain_allow(
        self, tmp_path: Path
    ) -> None:
        """The CI-shaped hole the board row names: the loader file EXISTS but
        the launch that would run the payload cannot READ it (0700/0750 home
        under a subordinate uid). Before the fix this fell through
        silently."""
        hidden = tmp_path / "landlock-loader.py"
        hidden.write_text("# not readable\n", encoding="utf-8")
        hidden.chmod(0o000)
        if os.access(str(hidden), os.R_OK):
            pytest.skip("running with privileges that ignore the file mode")
        result = self._run(
            tmp_path,
            "echo",
            "DF047-FS-OK",
            TERMINAL_JAIL_LANDLOCK_LOADER=str(hidden),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-OK" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr
        assert "cannot read" in result.stderr, result.stderr

    def test_missing_fs_loader_degrades_on_the_bwrap_plain_allow(
        self, tmp_path: Path
    ) -> None:
        result = self._run(
            tmp_path,
            "echo",
            "DF047-FS-OK",
            TERMINAL_JAIL_JAIL_BACKEND="bwrap",
            TERMINAL_JAIL_LANDLOCK_LOADER=str(tmp_path / "absent-loader.py"),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-OK" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr
        assert "not found" in result.stderr, result.stderr

    def test_unreadable_fs_loader_degrades_on_the_bwrap_plain_allow(
        self, tmp_path: Path
    ) -> None:
        hidden = tmp_path / "landlock-loader.py"
        hidden.write_text("# not readable\n", encoding="utf-8")
        hidden.chmod(0o000)
        if os.access(str(hidden), os.R_OK):
            pytest.skip("running with privileges that ignore the file mode")
        result = self._run(
            tmp_path,
            "echo",
            "DF047-FS-OK",
            TERMINAL_JAIL_JAIL_BACKEND="bwrap",
            TERMINAL_JAIL_LANDLOCK_LOADER=str(hidden),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-OK" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr
        assert "cannot read" in result.stderr, result.stderr

    def test_integrity_attach_prints_no_wrapper_degrade(self, tmp_path: Path) -> None:
        """Negative control: when the loader resolves and reads, the WRAPPER's
        degrade must NOT fire (the attach decision succeeded). Scoped to the
        wrapper's own two causes: the PLUGIN's engine-level degrade shares the
        warning prefix and may legitimately print on hosts whose checkout
        parent lacks o+x (the GH runner's — landlock.py's own
        _world_traversable rule), pre-existing behavior outside this seam."""
        result = self._run(tmp_path, "echo", "DF047-FS-INTACT")
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-INTACT" in result.stdout
        stderr = result.stderr
        assert "landlock-loader.py not found (searched" not in stderr, stderr
        assert "in the launch that would run it" not in stderr, stderr

    def test_knob_off_prints_no_fs_degrade_line(self, tmp_path: Path) -> None:
        """TERMINAL_JAIL_LANDLOCK=0 is the deliberate opt-out: no tier, no
        line (the degrade line's own remedy must actually silence it)."""
        result = self._run(
            tmp_path,
            "echo",
            "DF047-FS-OFF",
            TERMINAL_JAIL_LANDLOCK="0",
            TERMINAL_JAIL_LANDLOCK_LOADER=str(tmp_path / "absent-loader.py"),
        )
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-OFF" in result.stdout
        assert DEGRADE_PREFIX not in result.stderr, result.stderr


# ── Mapped arm: the CI-shaped hole, probe-gated with an honest skip ──────────

_TC = "--killchild"  # assembled: the wrapper pins the literal out of its
# own body for host content filters; the test assembles it the same way.


def _subid_start(path: str) -> int:
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == os.environ.get("USER", ""):
                if parts[1].isdigit():
                    return int(parts[1])
    except OSError:
        pass
    return 100000


def _mapped_launch_works() -> bool:
    """True when this host permits the wrapper's exact uid-mapped launch
    (setuid inside unprivileged user namespaces)."""
    probe = subprocess.run(
        [
            "unshare",
            "--user",
            f"--map-users=65534:{_subid_start('/etc/subuid')}:1",
            f"--map-groups=65534:{_subid_start('/etc/subgid')}:1",
            "-S",
            "65534",
            "-G",
            "65534",
            "--pid",
            "--fork",
            f"--{_TC}=SIGKILL",
            "true",
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    return probe.returncode == 0


HOST_DENIES_MAPPED = (
    "HOST-DENIES-MAPPED: this host denies setuid inside unprivileged user "
    "namespaces (the AppArmor 'unprivileged_userns' class), so the wrapper "
    "never promotes the mapped launch here; the CI-shaped Ubuntu runner that "
    "the board row names permits it — run this cell there"
)


class TestFsDegradeMappedArm:
    def test_missing_fs_loader_degrades_on_the_uid_mapped_plain_allow(
        self, tmp_path: Path
    ) -> None:
        """The mapped arm uses REAL unshare (no PATH stub): it only runs at
        all on a host that promotes the uid mapping, and there the missing
        loader must still print the named-cause line before the payload."""
        if not _mapped_launch_works():
            pytest.skip(HOST_DENIES_MAPPED)
        env = _base_env()
        env["TERMINAL_JAIL_LANDLOCK_LOADER"] = str(tmp_path / "absent-loader.py")
        result = _run_cli("--user", "echo", "DF047-FS-MAPPED", env=env, timeout=120)
        assert result.returncode == 0, result.stderr
        assert "DF047-FS-MAPPED" in result.stdout
        assert DEGRADE_PREFIX in result.stderr, result.stderr
        assert "not found" in result.stderr, result.stderr
