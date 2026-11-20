#!/usr/bin/env python3
"""Stage the two dogfood findings as boardctl create calls (argv-list form)."""

import subprocess

BOARD = "/home/kara/terminal-jail/.coding-hermes/board"

ROWS = [
    {
        "id": "TJ-DF-072",
        "title": "[P2] fs-tier launches print 'Landlock filesystem tier not applied ... commands run unchanged' while the kernel tier IS enforced - the in-launch attach warning contradicts the delivered containment",
        "priority": "P2",
        "complexity": "3",
        "type": "bug",
        "tags": "landlock,fs-tier,operator-surface,trust",
        "reasoning": (
            "Dogfood 2026-11-20 at HEAD e67e07e, dev host, two fresh installs. "
            "Decisive canary pair: `terminal-jail make canary` (cat of a mode-600 file at "
            "/run/user/1000/tj-canary, ungranted by the tier layout) exits rc=2 with `cat: "
            "/run/user/1000/tj-canary: Permission denied` under the DEFAULT tier, and the "
            "identical launch with TERMINAL_JAIL_LANDLOCK=0 reads the file (rc=0). One variable, "
            "so the auto-sandbox launch IS kernel-tiered on this host. The SAME tiered launches "
            "print `terminal-jail: WARNING: Landlock filesystem tier not applied (no "
            "caller-writable ungranted path for the enforcement probe); commands run unchanged "
            "without kernel filesystem enforcement ...` - that sentence is FALSE for this shape: "
            "containment is delivered. Mechanism: the tier trampoline applies the domain in the "
            "un-namespaced caller context (standalone/terminal-jail:1330-1342 comment states this "
            "is deliberate; the launch splice sits at :1650/_tj_fs_degrade sites :1676/:1747) and "
            "Landlock restrictions inherit across the namespace; the loader's OWN second attach "
            "inside the namespace then fails its enforcement probe (the mapped/overflow uid cannot "
            "write the probe at /run/user/1000) and prints the not-applied branch "
            "(standalone/landlock-loader.py:113-124) with no success line ever printed for the fs "
            "tier (the net tier has a 'kernel egress tier APPLIED' notice; the fs tier has no twin). "
            "An operator reading that warning believes they have NO fs containment when they HAVE it."
        ),
        "ac": (
            "1. A tiered auto-sandbox launch on this host class prints one line stating the fs tier "
            "IS enforced (an fs twin of the net tier's 'kernel egress tier APPLIED' notice) OR the "
            "in-launch not-applied branch stays silent when an ancestor Landlock domain is already "
            "active. "
            "2. The false 'commands run unchanged without kernel filesystem enforcement' sentence no "
            "longer prints in that shape; negative control: with TERMINAL_JAIL_LANDLOCK=0 the "
            "not-applied warning DOES still print. "
            "3. Both directions red-proved by the canary arm: `terminal-jail make canary` where the "
            "Makefile target cats a mode-600 file at /run/user/1000/tj-canary - denied under the "
            "tier, readable with TERMINAL_JAIL_LANDLOCK=0; evidence and probe scripts at "
            ".coding-hermes/evidence/2026-11-20-interpreter-contract/ (probe4_decisive.sh e1/e2, "
            "probe7_outside_tmp.sh f5)."
        ),
    },
    {
        "id": "TJ-DF-073",
        "title": "[P3] a broken explicit TERMINAL_JAIL_PYTHON pin surfaces the WRONG refusal box on every firewall-on invocation: 'interruptor-bridge-unavailable' (Fix text: run ./install.sh / set TERMINAL_JAIL_BRIDGE) shadows the documented 'interpreter-unavailable' box, with two raw bash exec-noise lines above it",
        "priority": "P3",
        "complexity": "2",
        "type": "bug",
        "tags": "interpreter-resolution,pin,refusal-surface,readable-refusal",
        "reasoning": (
            "Dogfood 2026-11-20 at HEAD e67e07e, fresh install into a throwaway HOME, installed CLI. "
            "Arms a3/a4/a5 (pin missing / not-executable / bare name not on PATH), each with the "
            "firewall ON (default): rc=126, stdout empty (payload NOT run), and stderr = (1) two raw "
            "bash noise lines (`terminal-jail: line 348: <pin>: No such file or directory` / "
            "`Permission denied` / `command not found`) leaked from the bridge exec inside the "
            "command substitution (standalone/terminal-jail:347-348), (2) the "
            "`COMMAND BLOCKED - interruptor-bridge-unavailable` box (:565) whose Fix text tells the "
            "user to `run ./install.sh from a checkout, or set TERMINAL_JAIL_BRIDGE` - the WRONG "
            "remedy for a pin fault, (3) the honest one-line fault note (:383-390) naming pin + cause "
            "+ 'no silent fallback'. The dedicated `COMMAND BLOCKED - interpreter-unavailable` box "
            "(:392-414, documented at specs/cli.md:404) is emitted only by _tj_require_interpreter "
            "called at :1404/:1582 - AFTER a successful bridge verdict - so with a broken pin it is "
            "unreachable in the default flow: the bridge itself (same pinned interpreter) fails "
            "first at :555. CHANGELOG RELEASE-TJ-021 promises the pin refusal as 'exit 126, "
            "interpreter-unavailable, naming the path and the cause' - rc and cause hold; the named "
            "surface never appears for a firewall-on user. The fault note saves honesty; the box "
            "misattributes and misremedies, and the noise lines break the readable-refusal "
            "discipline the product otherwise holds."
        ),
        "ac": (
            "1. With an explicitly broken pin (each fault class: missing path, non-executable file, "
            "bare name not on PATH) on a firewall-on invocation, stderr carries the "
            "'interpreter-unavailable' box - or, when a pin fault is detected, the bridge-unavailable "
            "handler's Fix text names the pin instead of install.sh/TERMINAL_JAIL_BRIDGE. "
            "2. No raw bash `line 347/348: ...` exec-noise lines print above the box in any of the "
            "three arms (readable-refusal discipline). "
            "3. Regression arms unchanged: rc stays 126 and stdout stays empty in enforce mode "
            "(payload never runs), and warn mode still degrades loudly and runs (a6 shape). "
            "Evidence: .coding-hermes/evidence/2026-11-20-interpreter-contract/ (probe2b_pins.sh "
            "a3/a4/a5/a6 + captured .out/.err per arm)."
        ),
    },
]

for r in ROWS:
    cmd = [
        "boardctl",
        "-C",
        BOARD,
        "create",
        "--id",
        r["id"],
        "--title",
        r["title"],
        "--type",
        r["type"],
        "--status",
        "pending",
        "--priority",
        r["priority"],
        "--complexity",
        r["complexity"],
        "--capability-tags",
        r["tags"],
        "--reasoning",
        r["reasoning"],
        "--acceptance-criteria",
        r["ac"],
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(r["id"], "rc=", res.returncode)
    print((res.stdout or "").strip()[:300])
    if res.returncode != 0:
        print("STDERR:", (res.stderr or "").strip()[:500])
