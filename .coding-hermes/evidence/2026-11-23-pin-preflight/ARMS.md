# TJ-DF-077 arm transcript — 2026-11-23, HEAD 838a0d5f, installed 1.3.4 (scratch HOME /tmp/tj-df-20261123a/home)

NOTE: the committed egress_probe2.py is the lint-reformatted copy (split/sorted
imports) of the script that produced the transcripts below; re-run bare it
prints the same control output (EXECUTABLE/PREFIX lines + DENIED errno=111
ECONNREFUSED), so the reformat is mechanical and output-identical.

Payload: egress_probe2.py (in this dir; the modification was auto-sandboxed on
every arm, so the payload ran under a uid-mapped launch when the tiers were on).

## Arm 1 — pin set, ambient PATH, tiers on  ->  DEFECT (raw death, no named verdict)

    env HOME=/tmp/tj-df-20261123a/home TERMINAL_JAIL_LANDLOCK_NET=1 \
        TERMINAL_JAIL_PYTHON=/usr/bin/python3 \
        <tj> python3 egress_probe2.py
    {"ts":"...","event":"verdict","action":"modify","rule_id":"auto-script","layer":"yaml","reason":"Command modified by auto-sandbox",...}
    [terminal-jail] Modified: 'python3' '/tmp/tj-df-20261123a/egress_p... → sandboxed
    terminal-jail: landlock: kernel filesystem tier APPLIED — ...
    terminal-jail: landlock-net: kernel egress tier APPLIED — TCP connect() restricted to ports [22, 53, 80, 443]; ...
    Fatal Python error: Failed to import encodings module
    Python runtime state: core initialized
    ModuleNotFoundError: No module named 'encodings'
    Current thread 0x000070092d6a8780 [python3] (most recent call first):
      <no Python frame>
    rc=1

NO terminal-jail named-cause line on any surface. (Identical death with
TERMINAL_JAIL_LANDLOCK_NET=0: the fs tier's read grant is the denier.)

## Arm 2 — same pin, TIERS OFF  ->  payload runs; proves the pin ≠ payload interpreter

    env HOME=... TERMINAL_JAIL_LANDLOCK=0 TERMINAL_JAIL_LANDLOCK_NET=0 \
        TERMINAL_JAIL_PYTHON=/usr/bin/python3 <tj> python3 egress_probe2.py
    ...verdict auto-script modify...
    EXECUTABLE=/home/kara/.hermes/installs/b0e47ae07995f891/environments/24f1df2ad984420181cb6be1707f6a03/venv/bin/python3
    PREFIX=/home/kara/.hermes/installs/b0e47ae07995f891/environments/24f1df2ad984420181cb6be1707f6a03/venv
    DENIED errno=111 (ECONNREFUSED) Connection refused
    rc=0

The payload ran the ambient-PATH harness venv python3, NOT the pinned
/usr/bin/python3. The pin covered the loader heads only.

## Arm 3 — clean PATH, no pin, fs tier on  ->  payload runs (coverable interpreter is fine)

    env PATH=/usr/bin:/bin HOME=... <tj> python3 egress_probe.py
    ...fs tier APPLIED...
    DENIED errno=111 (ECONNREFUSED) Connection refused
    rc=0

## Arm 4 — clean PATH, no pin, net tier on  ->  README-016 verified (EACCES)

    env PATH=/usr/bin:/bin HOME=... TERMINAL_JAIL_LANDLOCK_NET=1 <tj> python3 egress_probe.py
    ...fs + net tiers APPLIED...
    DENIED errno=13 (EACCES) Permission denied
    rc=0

Control (bare /usr/bin/python3, no jail): ECONNREFUSED — the EACCES in arm 4 is
the kernel net tier, not the empty port.

## Corroborating arm — pin-less ambient PATH still refuses with the NAMED verdict

    env HOME=... <tj> make ok            (ambient PATH python3 = harness venv)
    terminal-jail: auto-sandbox modify unavailable (the rewrite's payload starts
    with the interpreter 'python3' (/home/kara/.hermes/installs/.../venv/bin/python3),
    which the filesystem tier's Landlock domain cannot execute for 'make'; command
    not run — ... point TERMINAL_JAIL_PYTHON at an interpreter that lives under a
    prefix the filesystem tier's grant set covers (an absolute path alone is not
    the criterion: on Ubuntu 24.x-class hosts /usr/bin/python3 may dereference to
    a HOME-baked uv toolchain the grant set does not cover) or set
    TERMINAL_JAIL_LANDLOCK=0 ...)
    rc=2

## Environment notes

- Ambient PATH python3 on this host resolves to the harness venv under
  /home/kara/.hermes/installs/... (0700 ancestors) — the un-coverable shape.
- /usr/bin/python3 -> python3.14 (real system binary; its stdlib at
  /usr/lib/python3.14 is READABLE under the fs tier — a bash payload under the
  jail listed /usr/lib/python3.14/encodings/__init__.py successfully), which is
  why arm 3 runs and only the ambient interpreter dies.
