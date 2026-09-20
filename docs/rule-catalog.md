# Built-in rule catalog

<!-- GENERATED FILE — do not edit by hand.
     Regenerate:  python3 scripts/rule-catalog.py
     Drift gate:  python3 scripts/rule-catalog.py --check -->

This catalog is **generated** by `scripts/rule-catalog.py` from the shipped default rules file `plugin/terminal_jail/rules/00-builtins.yaml`. Editing it by hand achieves nothing — the next regeneration overwrites the edit. The rules file mirrors the engine constants (`BUILTIN_BLOCKLIST` / `BUILTIN_SANDBOX` / `BUILTIN_ALLOWLIST` in `plugin/terminal_jail/interruptor/`), and `plugin/test_packaging.py` enforces that the two stay identical (same ids, same patterns, same actions), so this catalog tracks the shipped engine.

## Totals

| Layer | Action | Priority | Rules |
|---|---|---|---:|
| Critical Blocklist | `block` | 1000 | 35 |
| Auto-Sandbox | `sandbox` | 700 | 9 |
| Always-Allow | `allow` | 500 | 10 |
| **Total** | | | **54** |

**54 built-in rules — 35 block + 9 sandbox + 10 allow.** To recount at any time: `python3 scripts/rule-catalog.py --check` re-derives these numbers from the rules file and exits 1 if the committed catalog has drifted from it.

## Rules by layer

### Critical Blocklist (`block`, priority 1000)

Verdict on match: block.

| Rule id | Scope |
|---|---|
| `builtin-kill-all` | Mass process kill |
| `builtin-killpg-pid1` | Process-group kill targeting PID 1 or own process group (killpg API) |
| `builtin-fork-bomb` | Fork bomb pattern (any function name, not just ':') |
| `builtin-rm-rf-root` | Recursive root filesystem removal |
| `builtin-dd-root` | Raw device write via dd |
| `builtin-mkfs` | Filesystem creation |
| `builtin-fdisk` | Partition manipulation |
| `builtin-chmod-777-root` | World-writable absolute path |
| `builtin-echo-to-system` | Redirect output to system paths |
| `builtin-curl-pipe-shell` | Curl/wget piping to shell |
| `builtin-sudo` | Privilege escalation via sudo/doas/su/pkexec |
| `builtin-code-injection` | Code-injection vectors in interpreter arguments (os.system, os.popen, shutil.rmtree, subprocess, eval, exec, __import__) |
| `builtin-indirect-shell` | Encoded/piped shell execution (base64 -d \| sh, printf-decode \| bash) |
| `builtin-vm-delete` | Bulk unlink or arbitrary execution via find (-delete / -exec / -ok) |
| `builtin-device-write` | Raw device writes outside dd (shred, wipefs, blkdiscard, urandom redirects) |
| `builtin-ns-escape` | Namespace/jail escape tooling (nsenter into a foreign PID, chroot, setpriv to uid 0, unshare -r) |
| `builtin-persistence` | Persistence install (crontab write, cron spool, rc.local, systemd unit drop) |
| `builtin-script-killall` | killall/pkill with SIGKILL (mass-kill by process name) |
| `builtin-interpreter-escape` | Interpreter destruction APIs (perl/ruby/node/python: unlink, rmtree, rm_rf, rmSync, execSync-masskill, fork loops) |
| `builtin-self-rewrite` | Self-modification vectors (rm/mv/redirect on terminal-jail's own rules and config) |
| `builtin-var-indirection` | Variable-indirection shell destruction (D=/; rm -rf $D and friends) |
| `builtin-net-devtcp-redirect` | Network-fd redirect reverse shell (/dev/tcp, /dev/udp) |
| `builtin-net-mkfifo-reverse-shell` | mkfifo feedback-loop reverse shell (fifo + shell + network client) |
| `builtin-net-nc-shell-attach` | netcat/ncat with a shell attach (-e/-c/--exec or a shell on either side of a pipe) |
| `builtin-net-socat-exec` | socat EXEC:/SYSTEM: wired to a network endpoint |
| `builtin-net-openssl-pipe-shell` | openssl s_client piped into a shell |
| `builtin-net-file-exfil-pipe` | Local-file reader piped into a bare raw-socket client (file exfiltration) |
| `builtin-net-file-exfil-redirect` | Bare raw-socket client fed a local file by an input redirect |
| `builtin-interp-egress-socket-shell` | Interpreter socket reverse shell (socket connect + fd duplication / pty) |
| `builtin-interp-egress-socket-file` | Interpreter raw-socket send of a local file (file exfiltration) |
| `builtin-interp-egress-http-file` | Interpreter HTTP upload of a local file (file exfiltration) |
| `builtin-net-curl-upload` | curl upload of a local file (file exfiltration) |
| `builtin-net-wget-post-file` | wget POST of a local file (file exfiltration) |
| `builtin-net-curl-form-upload` | curl multipart form upload of a local file (file exfiltration) |
| `builtin-net-remote-tree-copy` | Whole-tree or secret-source remote copy (root / secret-bearing source to a remote host) — DF-TERMINAL-JAIL-29 |

### Auto-Sandbox (`sandbox`, priority 700)

Verdict on match: rewrite into a namespace wrap (`modify`).

| Rule id | Scope |
|---|---|
| `auto-pytest` | Python test runner |
| `auto-npm-test` | JavaScript test runner |
| `auto-go-test` | Go test runner |
| `auto-make` | Build system |
| `auto-pip` | Package installer |
| `auto-cargo` | Rust build tool |
| `auto-gcc` | C/C++ compilation |
| `auto-script` | Script execution |
| `builtin-net-fetch-pipe-qualified` | Fetch pipeline into a path-qualified or wrapped interpreter |

### Always-Allow (`allow`, priority 500)

Verdict on match: allow; further evaluation stops.

| Rule id | Scope |
|---|---|
| `allow-echo` | Safe text output |
| `allow-ls` | Directory listing |
| `allow-pwd` | Print working directory |
| `allow-cat-safe` | Safe file reads (non-sensitive paths) |
| `allow-grep` | Text search |
| `allow-find-safe` | File search without -exec/-delete |
| `allow-git-read` | Git read operations |
| `allow-python-version` | Python version check |
| `allow-which` | Path resolution |
| `allow-cd` | Directory change |

## Reading the catalog

- The decider evaluates blocklist → allowlist → auto-sandbox → user rules; **first match wins**. Priorities order rules within a layer; they do not move a rule between layers.
- A user rule under `~/.config/terminal-jail/rules.d/` (or `/etc/terminal-jail/rules.d/`) whose id matches one of these ids **replaces** the built-in in its layer — that is the supported way to soften a built-in to `warn`. There is no way to remove one.
- A command matching **no** rule at all is ALLOWED (default-allow posture); `"rule_id": null` on an allow verdict is that case, not an approved decision.
- All built-in rules are `match: type: pattern` rules (regex over the command, engine matcher semantics: `re.search` with `re.IGNORECASE`).
- Opt-in rule packs install additional rules with `pack-<name>-*` ids and never grow this set (see README *Rule packs*).
