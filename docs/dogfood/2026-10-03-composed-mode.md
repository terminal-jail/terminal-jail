# 2026-10-03 — Composed mode (TJ-GAP-089) capture

Tool inside an outer containment layer: the container is the stand-in for a
bunker agent (bunker GAP-179). Outer layer measured first, then the tool's
own verdicts on the plain host and inside the container. Every block below is
raw command output from the capture run; nothing is transcribed by hand.

## Outer layer (docker python:3.11-slim, measured)

    readlink /proc/self/ns/pid  ==  /proc/1/ns/pid   (inside its own ns view)
    /.dockerenv present
    root mount fstype: overlay (/proc/self/mountinfo)
    cgroup v2 path: /   (/proc/self/cgroup)
    CapEff 00000000a80425fb  (bit 21 CAP_SYS_ADMIN clear)
    unshare --pid --fork --kill-child=SIGKILL --mount-proc true  -> rc=1 EPERM (~1ms)
    unshare --user --pid --fork ... true                          -> rc=1 EPERM (~2ms)

## Plain host (Ubuntu 26.04, kernel 7.0.0-31, apparmor_restrict_unprivileged_userns=1)

$ terminal-jail echo host-ok   # 0.17s, rc=0
  stdout:
    host-ok
$ terminal-jail rm -rf /   # 0.11s, rc=126
  stderr:
    +--------------------------------------------------------------+
    |  COMMAND BLOCKED — builtin-rm-rf-root                                
    +--------------------------------------------------------------+
    |  Recursive root directory removal (rm -rf /) is blocked.
    |
    |  Command: 'rm' '-rf' '/'
    |  Rule: builtin-rm-rf-root
    +--------------------------------------------------------------+
$ PATH=<no bwrap> terminal-jail --no-interruptor echo x   # 0.46s, rc=2
  stderr:
    terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user
    terminal-jail: cause: namespace creation needs privileges this context does not grant — a missing CAP_SYS_ADMIN (bit 21, e.g. inside a container: grep CapEff /proc/self/status) or a container seccomp/AppArmor profile denying unshare/unprivileged user namespaces (plain hosts: the AppArmor profile 'unprivileged_userns')
    terminal-jail: options: run on the outer host, grant inner namespace creation (allow CAP_SYS_ADMIN / permit the userns syscall in the container seccomp profile), or set TERMINAL_JAIL_COMPOSED=on to run with the firewall plus the outer layer's containment (composed mode, see README "Composed deployment")
$ TERMINAL_JAIL_COMPOSED=off PATH=<no bwrap> terminal-jail --no-interruptor echo x   # 0.03s, rc=2
  stderr:
    terminal-jail: namespace creation failed (unshare exit 1); command not run — on unprivileged hosts try --user
    terminal-jail: cause: namespace creation needs privileges this context does not grant — a missing CAP_SYS_ADMIN (bit 21, e.g. inside a container: grep CapEff /proc/self/status) or a container seccomp/AppArmor profile denying unshare/unprivileged user namespaces (plain hosts: the AppArmor profile 'unprivileged_userns')
    terminal-jail: options: run on the outer host, grant inner namespace creation (allow CAP_SYS_ADMIN / permit the userns syscall in the container seccomp profile), or set TERMINAL_JAIL_COMPOSED=on to run with the firewall plus the outer layer's containment (composed mode, see README "Composed deployment")
$ TERMINAL_JAIL_COMPOSED=on PATH=<no bwrap> terminal-jail --no-interruptor echo tj089-on-arm   # 0.46s, rc=0
  stderr:
    terminal-jail: WARNING: TERMINAL_JAIL_COMPOSED=on forced composed mode but no outer containment layer was detected — NO layer of this launch provides namespace isolation (operator decision)
    terminal-jail: COMPOSED MODE — running without an inner namespace
    terminal-jail: composed layers — jail_layer=platform claimed by operator override but NO outer layer detected: pid-namespace/proc NOT enforced by any layer in this launch; firewall: enforced by terminal-jail (interruptor verdict applied); seccomp: NOT applied by this tool; filesystem: NOT isolated by this tool
  stdout:
    tj089-on-arm

Host notes: auto selects bwrap here (installed + probe green), so the
unshare-failure arms use a PATH without bwrap — exactly the real container
shape. The bare-namespace refusal is reached only there.

## Inside the container (composed mode live)

$ docker run --rm -v <repo>:/repo:ro python:3.11-slim python3 /matrix.py   (matrix source: docs/dogfood record below)
    A echo rc=0 in 3.24s
       out: TJ089-INNER-OK | stderr lines: 6
    B block rc=126 in 3.07s
    C off rc=2 in 3.09s
    D backend=unshare rc=2
    E backend=bwrap rc=2
    F scripts/pidns-capability-probe.py rc=0 in 3.03s -> UNKNOWN: probe timed out after 3s
    F scripts/fs-isolation-probe.py rc=0 in 3.03s -> UNKNOWN: probe error: Command '['unshare', '--user', '--map-
    G make rc=127 in 3.11s | err1: ["[terminal-jail] Modified: 'make' '--version'... → sandboxed"]
    H on rc=0 in 3.11s | out: TJ089-ON
    CONTAINER MATRIX OK
    
Per-arm expectations verified by /tmp/tj089_container_matrix.py (worker-side):
A echo rc=0 composed; B rm -rf / rc=126 builtin-rm-rf-root; C composed=off
rc=2 refusal + cause + options; D TERMINAL_JAIL_JAIL_BACKEND=unshare rc=2
v1.1 refusal byte-identical; E backend=bwrap rc=2 not installed; F probe
scripts answer in ~3s (previously hung at 15s); G auto-sandbox rewrite runs
its payload composed; H TERMINAL_JAIL_COMPOSED=on rc=0.

## Probe fast-fail measurement (the 15s defect)

    Before (2026-10-01 evidence): ./standalone/terminal-jail echo  -> 15.26s, rc=2
                                  scripts/pidns-capability-probe.py -> 15.04s, "UNKNOWN: probe timed out after 15s"
    After  (this capture):         echo -> ~3.3s rc=0 composed; probes answer ~3.0s.

Attribution of the residual ~3s: the interruptor bridge's mapped-launch probe
(`unshare --user --map-users=…`) fails in ~2ms under bash but its forked child
survives as a zombie holding the capture pipe inside the container, so
subprocess.run(capture_output=True) waits out the probe budget — now 3s
(was 15s). The zombie does not outlive the container.
