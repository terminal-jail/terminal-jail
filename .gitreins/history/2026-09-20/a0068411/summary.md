# Verdict: TJ-GAP-062

**Task:** First rule pack db (FULL catalogue): psql escape, mysql SHUTDOWN, redis, mongosh, data-dir recursive-delete, dump exfil
**Evaluated:** 2026-09-20T21:17:30.531134
**Result:** ✓ PASS

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✓ **tier2**
  - COMPLETE
  ✓ Extend plugin/terminal_jail/rules/packs/db.yaml with the full pack-db-* catalogue (psql meta-shell escape, SQL destruction literals in execution context, mysqladmin shutdown, redis CONFIG/MODULE/FLUSHALL, mongosh dropDatabase/shutdown, recursive-delete on live data dirs, dump-to-network exfil), keep destructive-but-gray shapes at action=modify, keep all documented legit pins allow/modify with tests, ship plugin/test_rule_pack_db.py, full suite green: db.yaml now carries 14 rules (yaml load: rules:14 block:11 sandbox:3): pack-db-psql-meta-shell, pack-db-drop-database, pack-db-truncate-cascade, pack-db-admin-shutdown, pack-db-redis-config, pack-db-redis-module, pack-db-redis-flush, pack-db-mongosh-drop, pack-db-mongosh-shutdown, pack-db-data-dir-delete, pack-db-dump-exfil (block@950); pack-db-drop-table, pack-db-truncate, pack-db-dump-restore (sandbox@650). Live intercept() probe with the pack installed into a scratch rules dir: psql -c '\! id' -> block pack-db-psql-meta-shell; psql -c 'DROP DATABASE prod' -> block pack-db-drop-database; mysqladmin shutdown -> block pack-db-admin-shutdown; redis-cli CONFIG SET dir /tmp -> block pack-db-redis-config; redis-cli MODULE LOAD -> block pack-db-redis-module; redis-cli FLUSHALL -> block pack-db-redis-flush; mongosh --eval 'db.dropDatabase()' -> block pack-db-mongosh-drop; mongosh --eval 'db.adminCommand({shutdown:1})' -> block pack-db-mongosh-shutdown; rm -rf /var/lib/postgresql/16/main -> block pack-db-data-dir-delete; 'pg_dump' 'db' '|' 'nc' 'h' 'p' -> block pack-db-dump-exfil. Gray shapes at modify: psql -c 'DROP TABLE users' -> modify pack-db-drop-table (modified=True, unshare wrap); psql -c 'TRUNCATE users' -> modify pack-db-truncate; pg_dump mydb / pg_restore -> modify pack-db-dump-restore. Legit pins allow: psql -c 'SELECT 1', psql -f migrations/002_legacy.sql, sqlite3 state.db 'INSERT ...', alembic upgrade head, python -c 'import sqlalchemy', redis-cli GET/SET/CONFIG GET, mysqladmin status all -> allow rule=None; pg_dump mydb -> modify pack-db-dump-restore. False-positive contexts (sed/git-commit/grep/echo) -> no pack-* attribution. plugin/test_rule_pack_db.py shipped (524 lines, 108 tests PASS). Full suite: `.venv/bin/python -m pytest -q` -> '1348 passed, 7 skipped in 31.95s' (exit 0); baseline at 5d79ff5^ -> '1226 passed, 7 skipped' => +122 tests, zero regressions. ruff check on both test files: 'All checks passed!'. scripts/rule-pack-tool.py validate: 'pack db valid — 14 rule(s) (11 block, 3 sandbox)' with no id collisions. LSP diagnostics: none.


## Summary

Judge Result: TJ-GAP-062

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: PASS
  COMPLETE
  ✓ Extend plugin/terminal_jail/rules/packs/db.yaml with the full pack-db-* catalogue (psql meta-shell escape, SQL destruction literals in execution context, mysqladmin shutdown, redis CONFIG/MODULE/FLUSHALL, mongosh dropDatabase/shutdown, recursive-delete on live data dirs, dump-to-network exfil), keep destructive-but-gray shapes at action=modify, keep all documented legit pins allow/modify with tests, ship plugin/test_rule_pack_db.py, full suite green: db.yaml now carries 14 rules (yaml load: rules:14 block:11 sandbox:3): pack-db-psql-meta-shell, pack-db-drop-database, pack-db-truncate-cascade, pack-db-admin-shutdown, pack-db-redis-config, pack-db-redis-module, pack-db-redis-flush, pack-db-mongosh-drop, pack-db-mongosh-shutdown, pack-db-data-dir-delete, pack-db-dump-exfil (block@950); pack-db-drop-table, pack-db-truncate, pack-db-dump-restore (sandbox@650). Live intercept() probe with the pack installed into a scratch rules dir: psql -c '\! id' -> block pack-db-psql-meta-shell; psql -c 'DROP DATABASE prod' -> block pack-db-drop-database; mysqladmin shutdown -> block pack-db-admin-shutdown; redis-cli CONFIG SET dir /tmp -> block pack-db-redis-config; redis-cli MODULE LOAD -> block pack-db-redis-module; redis-cli FLUSHALL -> block pack-db-redis-flush; mongosh --eval 'db.dropDatabase()' -> block pack-db-mongosh-drop; mongosh --eval 'db.adminCommand({shutdown:1})' -> block pack-db-mongosh-shutdown; rm -rf /var/lib/postgresql/16/main -> block pack-db-data-dir-delete; 'pg_dump' 'db' '|' 'nc' 'h' 'p' -> block pack-db-dump-exfil. Gray shapes at modify: psql -c 'DROP TABLE users' -> modify pack-db-drop-table (modified=True, unshare wrap); psql -c 'TRUNCATE users' -> modify pack-db-truncate; pg_dump mydb / pg_restore -> modify pack-db-dump-restore. Legit pins allow: psql -c 'SELECT 1', psql -f migrations/002_legacy.sql, sqlite3 state.db 'INSERT ...', alembic upgrade head, python -c 'import sqlalchemy', redis-cli GET/SET/CONFIG GET, mysqladmin status all -> allow rule=None; pg_dump mydb -> modify pack-db-dump-restore. False-positive contexts (sed/git-commit/grep/echo) -> no pack-* attribution. plugin/test_rule_pack_db.py shipped (524 lines, 108 tests PASS). Full suite: `.venv/bin/python -m pytest -q` -> '1348 passed, 7 skipped in 31.95s' (exit 0); baseline at 5d79ff5^ -> '1226 passed, 7 skipped' => +122 tests, zero regressions. ruff check on both test files: 'All checks passed!'. scripts/rule-pack-tool.py validate: 'pack db valid — 14 rule(s) (11 block, 3 sandbox)' with no id collisions. LSP diagnostics: none.


Overall: PASS ✓
