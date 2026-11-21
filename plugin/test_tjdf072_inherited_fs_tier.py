"""TJ-DF-072 — an in-namespace loader re-attach reports INHERITED enforcement.

The defect: a tiered auto-sandbox launch applies the Landlock domain in the
un-namespaced CALLER context (the wrapper's trampoline). Landlock restriction
INHERITS across the namespace boundary, so the payload IS contained — but the
loader that re-attaches inside the namespace cannot re-prove the property
(the inherited domain denies every probe host) and used to print

    terminal-jail: WARNING: Landlock filesystem tier not applied (...);
    commands run unchanged without kernel filesystem enforcement ...

which is FALSE for that shape. The net (egress) tier already prints a
"kernel egress tier APPLIED" notice; the fs tier had no twin.

Doctrine under test (the loader-side twin of TJ-DF-064 / ae8524e6):

* EVIDENCE, NEVER INTENT — the marker is written by the loader only AFTER a
  proven apply, and it is trusted only together with the kernel's NoNewPrivs
  flag (set by every Landlock apply, inherits across exec + the namespace
  boundary, cannot be cleared from userspace). A launch that merely WANTS the
  tier cannot manufacture either half;
* a launch with NO ancestor domain keeps the loud not-applied warning, and
  TERMINAL_JAIL_LANDLOCK=0 stays silent (the disable is deliberate);
* containment is untouched: the canary is still DENIED under the tier, and
  with the tier off it is still readable (one variable).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from terminal_jail.interruptor import landlock as ll
from terminal_jail.interruptor import landlock_net as ll_net

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOADER_SCRIPT = PROJECT_ROOT / "standalone" / "landlock-loader.py"
BUNDLED_LOADER = (
    PROJECT_ROOT / "plugin" / "terminal_jail" / "_bundled" / "landlock-loader.py"
)
TIER_MODULE = PROJECT_ROOT / "plugin" / "terminal_jail" / "interruptor" / "landlock.py"

FALSE_SENTENCE = "commands run unchanged without kernel filesystem enforcement"
WARNING_PREFIX = "terminal-jail: WARNING: Landlock filesystem tier not applied"
APPLIED_LINE = "kernel filesystem tier APPLIED"
INHERITED_ENV = "TERMINAL_JAIL_LANDLOCK_INHERITED"

HOST_DEGRADED = "HOST-DEGRADED-LANDLOCK"

GENUINE_MESSAGE = (
    f"{WARNING_PREFIX} (no caller-writable ungranted path for the enforcement "
    f"probe); {FALSE_SENTENCE} — classify the host with "
    "scripts/landlock-capability-probe.py and verify the loader path and "
    "launch context; do not disable filesystem protection to suppress this "
    "warning"
)


def _load_loader() -> ModuleType:
    """Import the loader SCRIPT as a module (it guards ``__main__``)."""
    spec = importlib.util.spec_from_file_location("tj_loader_under_test", LOADER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _probe_host_allows_landlock() -> bool:
    """FULL enforcement available here (the suite's HOST-DEGRADED doctrine)."""
    probe = PROJECT_ROOT / "scripts" / "landlock-capability-probe.py"
    try:
        result = subprocess.run(
            [sys.executable, str(probe), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    return '"verdict": "FULL"' in result.stdout.replace("\n", " ") or (
        '"FULL"' in result.stdout and '"verdict"' in result.stdout
    )


def _unshare_user_namespace_works() -> bool:
    """Can this host still enter the legacy (mapping-less) namespace shape?"""
    unshare = shutil.which("unshare")
    if unshare is None:
        return False
    try:
        result = subprocess.run(
            [unshare, "--user", "--pid", "--fork", "true"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


# ── The evidence seam: what counts as "an ancestor domain is active" ──────


class TestInheritedEvidenceSeam:
    def test_marker_plus_kernel_flag_reports_the_enforced_tier(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        loader = _load_loader()
        monkeypatch.setenv(INHERITED_ENV, "1")
        monkeypatch.setattr(loader, "_no_new_privs_set", lambda: True)
        loader._report_not_applied(GENUINE_MESSAGE)
        err = capsys.readouterr().err
        assert APPLIED_LINE in err
        assert FALSE_SENTENCE not in err
        assert WARNING_PREFIX not in err

    def test_marker_alone_is_not_evidence(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A stale/forged marker without the kernel flag must NOT silence."""
        loader = _load_loader()
        monkeypatch.setenv(INHERITED_ENV, "1")
        monkeypatch.setattr(loader, "_no_new_privs_set", lambda: False)
        loader._report_not_applied(GENUINE_MESSAGE)
        err = capsys.readouterr().err
        assert GENUINE_MESSAGE in err
        assert APPLIED_LINE not in err

    def test_kernel_flag_alone_is_not_evidence(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The genuine degraded shape: hardened lineage, but no proven attach.

        This is the negative control AC2 depends on — the not-applied warning
        (including the "commands run unchanged" sentence) still prints.
        """
        loader = _load_loader()
        monkeypatch.delenv(INHERITED_ENV, raising=False)
        monkeypatch.setattr(loader, "_no_new_privs_set", lambda: True)
        loader._report_not_applied(GENUINE_MESSAGE)
        err = capsys.readouterr().err
        assert WARNING_PREFIX in err
        assert FALSE_SENTENCE in err
        assert APPLIED_LINE not in err

    def test_no_evidence_at_all_warns(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        loader = _load_loader()
        monkeypatch.delenv(INHERITED_ENV, raising=False)
        monkeypatch.setattr(loader, "_no_new_privs_set", lambda: False)
        loader._report_not_applied(GENUINE_MESSAGE)
        err = capsys.readouterr().err
        assert GENUINE_MESSAGE in err
        assert APPLIED_LINE not in err

    def test_no_new_privs_reader_is_fail_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unreadable /proc must not turn into "evidence present"."""
        loader = _load_loader()

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("no /proc in this shape")

        monkeypatch.setattr("builtins.open", _boom)
        assert loader._no_new_privs_set() is False

    def test_applied_notice_twins_the_net_tier_notice(self) -> None:
        """The fs APPLIED line matches the net tier's tone and contract."""
        loader = _load_loader()
        notice = loader._applied_notice()
        assert APPLIED_LINE in notice
        assert "terminal-jail: landlock:" in notice
        assert (
            "EACCES/EPERM from open() below this line is the KERNEL denying" in notice
        )
        assert "TJ-GAP-082" in notice
        assert FALSE_SENTENCE not in notice
        # The net twin says the same thing about connect(); both name the
        # kernel as the denier and the interruptor as the excluded cause.
        net = ll_net.kernel_denial_notice([443])
        assert "kernel egress tier APPLIED" in net
        for fragment in ("is the KERNEL denying", "not an interruptor rule verdict"):
            assert fragment in notice
            assert fragment in net

    def test_loader_keeps_one_reporting_exit(self) -> None:
        """No path may print the false sentence outside ``_report_not_applied``."""
        text = LOADER_SCRIPT.read_text(encoding="utf-8")
        assert text.count(FALSE_SENTENCE) == 1
        assert "_report_not_applied(" in text
        # The marker is written only on the PROVEN branch.
        assert 'os.environ[_INHERITED_ENV] = "1"' in text
        assert "if applied:" in text

    def test_bundled_copy_is_byte_identical(self) -> None:
        assert LOADER_SCRIPT.read_bytes() == BUNDLED_LOADER.read_bytes()


# ── The marker is written only after a PROVEN apply ───────────────────────


def _stub_tree(tmp_path: Path, apply_tier_body: str) -> Path:
    """A loader copy next to a STUB tier module (no kernel, deterministic)."""
    root = tmp_path / "pkg"
    (root / "interruptor").mkdir(parents=True)
    loader = root / "landlock-loader.py"
    loader.write_text(LOADER_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "interruptor" / "landlock.py").write_text(
        "def apply_tier():\n" + apply_tier_body, encoding="utf-8"
    )
    return loader


def _run_loader(
    loader: Path, payload: list[str], extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env.pop(INHERITED_ENV, None)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(loader), *payload],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        cwd=str(loader.parent),
        env=env,
    )


MARKER_PAYLOAD = ["sh", "-c", f"echo marker=${{{INHERITED_ENV}-<unset>}}"]


class TestMarkerOnlyAfterProof:
    def test_proven_apply_exports_the_marker(self, tmp_path: Path) -> None:
        loader = _stub_tree(tmp_path, '    return True, ""\n')
        result = _run_loader(loader, MARKER_PAYLOAD)
        assert result.returncode == 0
        assert "marker=1" in result.stdout
        assert WARNING_PREFIX not in result.stderr
        assert APPLIED_LINE not in result.stderr

    def test_unproven_apply_never_exports_the_marker(self, tmp_path: Path) -> None:
        loader = _stub_tree(
            tmp_path,
            '    return False, "the enforcement probe could not run"\n',
        )
        result = _run_loader(loader, MARKER_PAYLOAD)
        assert result.returncode == 0
        assert "marker=<unset>" in result.stdout
        assert WARNING_PREFIX in result.stderr
        assert FALSE_SENTENCE in result.stderr
        assert APPLIED_LINE not in result.stderr

    def test_disabled_knob_stays_silent_and_unmarked(self, tmp_path: Path) -> None:
        loader = _stub_tree(tmp_path, '    return False, ""\n')
        result = _run_loader(loader, MARKER_PAYLOAD, {"TERMINAL_JAIL_LANDLOCK": "0"})
        assert result.returncode == 0
        assert "marker=<unset>" in result.stdout
        assert "Landlock" not in result.stderr

    def test_inherited_marker_from_an_ancestor_reaches_the_payload(
        self, tmp_path: Path
    ) -> None:
        """An inherited marker is visible to the nested attach (propagation)."""
        loader = _stub_tree(tmp_path, '    return True, ""\n')
        result = _run_loader(loader, MARKER_PAYLOAD, {INHERITED_ENV: "1"})
        assert "marker=1" in result.stdout


# ── Kernel arms: the canary stays red, and the line tells the truth ───────


def _nested_rig(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """home + workdir (cwd grant) holding the loader and its tier module."""
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    (work / "interruptor").mkdir(parents=True)
    loader = work / "landlock-loader.py"
    loader.write_text(LOADER_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (work / "interruptor" / "landlock.py").write_text(
        TIER_MODULE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    secret = tmp_path / "s600"  # OUTSIDE home/work: ungranted by the layout
    secret.write_text("TJ-DF-072-CANARY\n", encoding="utf-8")
    os.chmod(secret, 0o600)
    return home, work, loader, secret


def _rig_env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("TERMINAL_JAIL_")}
    env.pop(INHERITED_ENV, None)
    for drop in ("XDG_RUNTIME_DIR", "TMPDIR", "TEMP", "TMP", "XDG_CACHE_HOME"):
        env.pop(drop, None)
    env["HOME"] = str(home)
    env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    return env


CANARY = ["sh", "-c", "cat {secret}; echo read_rc=$?"]


def test_inherited_reattach_reports_enforced_and_still_denies(tmp_path: Path) -> None:
    """The production nesting: outer attach proves → namespace → re-attach."""
    if not _probe_host_allows_landlock():
        pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
    if not _unshare_user_namespace_works():
        pytest.skip("HOST-DEGRADED-USERNS: the namespace shape is blocked here")
    home, work, loader, secret = _nested_rig(tmp_path)
    inner = [
        "sh",
        "-c",
        f"cat {secret}; echo read_rc=$?",
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(loader),
            "--",
            "unshare",
            "--user",
            "--pid",
            "--fork",
            "--kill-child=SIGKILL",
            "/usr/bin/python3",
            "-S",
            str(loader),
            "--",
            *inner,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=str(work),
        env=_rig_env(home),
    )
    assert APPLIED_LINE in result.stderr, result.stderr
    assert FALSE_SENTENCE not in result.stderr, result.stderr
    assert WARNING_PREFIX not in result.stderr, result.stderr
    assert "read_rc=1" in result.stdout, (result.stdout, result.stderr)
    assert "TJ-DF-072-CANARY" not in result.stdout


def test_no_ancestor_still_warns_and_stays_unenforced(tmp_path: Path) -> None:
    """Negative control: no ancestor domain ⇒ warning + the read SUCCEEDS."""
    if not _unshare_user_namespace_works():
        pytest.skip("HOST-DEGRADED-USERNS: the namespace shape is blocked here")
    home, work, loader, secret = _nested_rig(tmp_path)
    result = subprocess.run(
        [
            "unshare",
            "--user",
            "--pid",
            "--fork",
            "--kill-child=SIGKILL",
            "/usr/bin/python3",
            "-S",
            str(loader),
            "--",
            "sh",
            "-c",
            f"cat {secret}; echo read_rc=$?",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=str(work),
        env=_rig_env(home),
    )
    assert WARNING_PREFIX in result.stderr, result.stderr
    assert FALSE_SENTENCE in result.stderr, result.stderr
    assert APPLIED_LINE not in result.stderr, result.stderr
    assert "TJ-DF-072-CANARY" in result.stdout
    assert "read_rc=0" in result.stdout


def test_tier_off_launch_is_unenforced(tmp_path: Path) -> None:
    """AC2's other arm: TERMINAL_JAIL_LANDLOCK=0 ⇒ readable, silently."""
    if not _probe_host_allows_landlock():
        pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
    home, work, loader, secret = _nested_rig(tmp_path)
    env = _rig_env(home)
    env["TERMINAL_JAIL_LANDLOCK"] = "0"
    result = subprocess.run(
        [
            sys.executable,
            str(loader),
            "--",
            "sh",
            "-c",
            f"cat {secret}; echo read_rc=$?",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=str(work),
        env=env,
    )
    assert "TJ-DF-072-CANARY" in result.stdout
    assert "read_rc=0" in result.stdout
    assert "Landlock" not in result.stderr
    assert ll.landlock_enabled_from_environment() is True  # ambient env untouched
