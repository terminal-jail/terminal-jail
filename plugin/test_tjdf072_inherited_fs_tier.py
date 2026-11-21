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
  with the tier off it is still readable (one variable). The deny arm's
  canary HOST is derived from the tier's own grant set at runtime: a canary
  parked under a granted root (e.g. ``/tmp``, which ``build_layout`` grants
  as a write root) reads fine under full enforcement, so the deny could not
  fire there and a green run would be placement luck.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
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

CANARY_TEXT = "TJ-DF-072-CANARY\n"
CANARY_NAME = "s600"
SCRATCH_PREFIX = "tjdf072-canary-"

# Knobs the loader CHILD does not see (`_rig_env` strips them), so they must
# not colour the grant set this module derives either.
_CHILD_STRIPPED_ENV = ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR")


def _rig_anchors(tmp_path: Path) -> tuple[Path, Path]:
    """home + workdir — the two directories the tier layout anchors on."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    work = tmp_path / "work"
    (work / "interruptor").mkdir(parents=True, exist_ok=True)
    return home, work


def _tier_grant_roots(home: Path, work: Path) -> list[Path]:
    """The grant roots the tier ACTUALLY enforces for this rig.

    Derived by the tier's own layout code — not a hardcoded guess — with the
    same environment the loader child receives (``_rig_env`` strips the temp
    and XDG knobs, so ``TMPDIR`` must not leak into the answer). ``workdir``
    plus the write/read/read-dir roots are the whole allowlist; every path
    outside them is denied by omission.
    """
    saved = {
        name: os.environ.pop(name) for name in _CHILD_STRIPPED_ENV if name in os.environ
    }
    try:
        layout = ll.build_layout(workdir=str(work), home=str(home), payload_argv=[])
    finally:
        os.environ.update(saved)
    assert layout is not None, "the rig anchors must yield a layout"
    return [
        Path(os.path.realpath(p))
        for p in (
            layout.workdir,
            *layout.write_roots,
            *layout.read_roots,
            *layout.read_dir_roots,
        )
    ]


def _inside(path: Path, root: Path) -> bool:
    """True when ``path`` is ``root`` or lives beneath it (realpaths)."""
    real, base = Path(os.path.realpath(path)), Path(os.path.realpath(root))
    return real == base or base in real.parents


def _covered(path: Path, roots: list[Path]) -> bool:
    return any(_inside(path, root) for root in roots)


def _writable_dir(path: Path) -> bool:
    try:
        return path.is_dir() and os.access(path, os.W_OK | os.X_OK)
    except OSError:
        return False


def _pick_canary_host(
    tmp_path: Path, home: Path, work: Path
) -> tuple[Path | None, str, bool]:
    """A caller-writable directory the tier does NOT grant.

    The deny arm is only evidence where the canary is DENIED by the layout:
    a canary under a granted root reads fine under full enforcement, so the
    arm would pass (or fail) on placement luck. ``build_layout`` puts the
    temp dirs (``/tmp``, ``/var/tmp``, TMPDIR/TMP/TEMP) in the WRITE grant
    set unconditionally, so a basetemp living under any of them is granted —
    which is exactly how ``tmp_path / "s600"`` turned into a CI red.
    ``layout.ungranted_paths`` cannot be used to decide this: it lists the
    basetemp's PARENT (``home_parent``) while the ``/tmp`` write root shadows
    it, so the question is asked of the grant roots.

    Returns ``(host, reason, created)`` — ``host`` is None with ``reason``
    naming what was tried when this host has no such directory (the caller
    then skips loudly: the property cannot be proven without one), and
    ``created`` tells the caller to remove a directory this probe made.
    """
    assert home.is_dir() and work.is_dir(), "rig anchors must exist first"
    roots = _tier_grant_roots(home, work)
    tried: list[str] = []

    def _take(candidate: Path) -> Path | None:
        text = str(candidate)
        if text not in tried:
            tried.append(text)
        if not _writable_dir(candidate) or _covered(candidate, roots):
            return None
        return candidate

    # 1) The basetemp itself, whenever the layout happens not to grant it —
    #    the default host (basetemp under a non-temp TMPDIR) stays on this
    #    arm, so nothing is created and pytest's own disposal is the cleanup.
    #    The two rig anchors are granted BY CONSTRUCTION (``work`` is the
    #    workdir grant, ``home`` is a read-dir root), so they are never
    #    candidates: everything under them is covered by omission.
    chosen = _take(tmp_path)
    if chosen is not None:
        return chosen, "", False

    # 2) Caller-owned runtime dirs (outside every grant on a normal session).
    for raw in (os.environ.get("XDG_RUNTIME_DIR", ""), f"/run/user/{os.getuid()}"):
        if raw.startswith("/"):
            chosen = _take(Path(raw))
            if chosen is not None:
                return chosen, "", False

    # 3) Caller-owned temp dirs — usable only where the child's grant set
    #    does not include them (i.e. a TMPDIR the loader does not see).
    for name in ("TMPDIR", "TMP", "TEMP"):
        raw = os.environ.get(name, "").strip()
        if raw.startswith("/"):
            chosen = _take(Path(raw))
            if chosen is not None:
                return chosen, "", False

    # 4) Directories this probe creates, removed by the caller when unused.
    for parent in (PROJECT_ROOT.parent, Path(os.path.expanduser("~"))):
        tried.append(str(parent))
        try:
            made = Path(tempfile.mkdtemp(prefix=SCRATCH_PREFIX, dir=str(parent)))
        except OSError:
            continue
        chosen = _take(made)
        if chosen is not None:
            return chosen, "", True
        shutil.rmtree(made, ignore_errors=True)

    # 5) The shapes that made this a defect: the basetemp, its ancestors, and
    #    the kernel temp roots. Probed (cheaply) so the reason names them.
    for candidate in (tmp_path, *tmp_path.parents, Path("/var/tmp"), Path("/tmp")):
        _take(candidate)

    reason = (
        f"no caller-writable directory outside the tier's {len(roots)} grant "
        f"roots (tried: {', '.join(tried)})"
    )
    return None, reason, False


@contextlib.contextmanager
def _canary_host(tmp_path: Path) -> Iterator[tuple[Path | None, str, bool]]:
    home, work = _rig_anchors(tmp_path)
    host, reason, created = _pick_canary_host(tmp_path, home, work)
    try:
        yield host, reason, created
    finally:
        if host is not None:
            try:
                (host / CANARY_NAME).unlink()
            except OSError:
                pass
            if created:
                shutil.rmtree(host, ignore_errors=True)


@pytest.fixture
def ungranted_canary(tmp_path: Path) -> Iterator[Path]:
    """Deny-arm fixture: a writable canary host the layout does NOT grant.

    Skips LOUDLY (the probe7 f5 rule) when this host has none — the deny
    property cannot be proven, and a silent pass would be placement luck.
    """
    with _canary_host(tmp_path) as (host, reason, _created):
        if host is None:
            pytest.skip(f"{GENUINE_MESSAGE} [{reason}]")
        yield host


@pytest.fixture
def readable_canary(tmp_path: Path) -> Iterator[Path]:
    """Read-arm fixture: prefer an ungranted host, fall back to ``tmp_path``.

    The read arms assert the canary SUCCEEDS (no ancestor domain / tier off).
    An ungranted host makes that a real contrast; where none exists the claim
    is weaker but still exercised (the file must exist and be readable), so
    the fallback is taken instead of skipping a true statement.
    """
    with _canary_host(tmp_path) as (host, _reason, _created):
        yield host if host is not None else tmp_path


def _nested_rig(
    tmp_path: Path, canary_host: Path, *, require_ungranted: bool
) -> tuple[Path, Path, Path, Path]:
    """home + workdir (cwd grant) holding the loader and its tier module.

    The canary lives at ``canary_host / s600`` — DERIVED by the caller from
    the tier's grant set, never assumed to be ``tmp_path``. With
    ``require_ungranted`` (the deny arm) the placement is asserted against
    the layout so a green run cannot be placement luck; without it (the read
    arms) only the readability premise is asserted.
    """
    home, work = _rig_anchors(tmp_path)
    loader = work / "landlock-loader.py"
    loader.write_text(LOADER_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (work / "interruptor" / "landlock.py").write_text(
        TIER_MODULE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    secret = canary_host / CANARY_NAME
    if require_ungranted:
        roots = _tier_grant_roots(home, work)
        assert not _covered(secret, roots), (
            f"canary {secret} sits under a tier grant root — the deny arm "
            f"could not fire: {[str(r) for r in roots if _covered(secret, [r])]}"
        )
    secret.write_text(CANARY_TEXT, encoding="utf-8")
    os.chmod(secret, 0o600)
    # Premise: OUTSIDE the tier this uid can read the canary, so any denial
    # below can only be the kernel's (never DAC).
    assert secret.read_text(encoding="utf-8") == CANARY_TEXT
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


def test_inherited_reattach_reports_enforced_and_still_denies(
    tmp_path: Path, ungranted_canary: Path
) -> None:
    """The production nesting: outer attach proves → namespace → re-attach."""
    if not _probe_host_allows_landlock():
        pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
    if not _unshare_user_namespace_works():
        pytest.skip("HOST-DEGRADED-USERNS: the namespace shape is blocked here")
    home, work, loader, secret = _nested_rig(
        tmp_path, ungranted_canary, require_ungranted=True
    )
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


def test_no_ancestor_still_warns_and_stays_unenforced(
    tmp_path: Path, readable_canary: Path
) -> None:
    """Negative control: no ancestor domain ⇒ warning + the read SUCCEEDS."""
    if not _unshare_user_namespace_works():
        pytest.skip("HOST-DEGRADED-USERNS: the namespace shape is blocked here")
    home, work, loader, secret = _nested_rig(
        tmp_path, readable_canary, require_ungranted=False
    )
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


def test_tier_off_launch_is_unenforced(tmp_path: Path, readable_canary: Path) -> None:
    """AC2's other arm: TERMINAL_JAIL_LANDLOCK=0 ⇒ readable, silently."""
    if not _probe_host_allows_landlock():
        pytest.skip(f"{HOST_DEGRADED}: Landlock enforcement unavailable here")
    home, work, loader, secret = _nested_rig(
        tmp_path, readable_canary, require_ungranted=False
    )
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
