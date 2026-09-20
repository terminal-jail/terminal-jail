# Verdict: DF-TERMINAL-JAIL-23

**Task:** db pack block rules match DROP statements in execution context, not bare statement text
**Evaluated:** 2026-09-20T18:32:58.570055
**Result:** ✗ FAIL

## Pipeline Stages

- ✓ **tier1**
  -   ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================
- ✗ **tier2**
  - INCOMPLETE
  ✓ plugin/terminal_jail/rules/packs/db.yaml constrains the pack-db-drop-database and pack-db-drop-table block rules to a SQL execution context: each is a composite/and rule requiring a SQL client token plus the statement in execution position: PASS: db.yaml pack-db-drop-database (line ~85) and pack-db-drop-table (~110) both use match.type=composite, operator=and, with condition 1 = SQL client token regex (psql|mysql|mariadb|sqlite3|mysqladmin|sqlplus) and condition 2 = execution-position regex (-c/-e/--command/--execute arms A/B1/B2/C).
  ✓ Through intercept() with the pack installed, psql -c DROP DATABASE, psql -c DROP TABLE and mysql -e DROP TABLE each return action block with the matching pack-db-drop-* rule id: PASS: live intercept() with pack installed: psql -c "DROP DATABASE prod" -> block/pack-db-drop-database; psql -c "DROP TABLE users" -> block/pack-db-drop-table; mysql -e "DROP TABLE users;" -> block/pack-db-drop-table.
  ✓ Through intercept() with the pack installed, the four documented false-positive shapes (sed -i substitution text, git commit -m message text, a read-only SELECT whose quoted literal merely contains the phrase, and echo redirecting the phrase to a file) return no pack-db-* attribution: PASS: live intercept() with pack installed: sed -i substitution -> allow/None; git commit -am -> allow/None; psql -c SELECT with quoted literal 'drop database retry' -> allow/None; echo "DROP TABLE users" > file -> allow/allow-echo. No pack-db-* attribution on any.
  ✗ plugin/test_rule_packs.py carries a regression class exercising the block and allow shapes with the installed-pack fixture, and the full suite passes with only the new tests added (zero regressions): Not verified — evaluation terminated before this criterion was checked
  ✗ CHANGELOG.md and the pack header document the accepted residuals: the -f file body remains DF-TERMINAL-JAIL-10, and destructive SQL pasted into a non-SQL-client interpreter is no longer caught: Not verified — evaluation terminated before this criterion was checked
Partial verdict — evaluation hit resource cap before all criteria verified

## Summary

Judge Result: DF-TERMINAL-JAIL-23

Stage tier1: PASS
    ✓ lint: ok (no output)
  ✓ secrets: secrets: harness state excluded from gitleaks scope (.gitreins/**)
  ✓ tests: ============================= test session starts ==============================

Stage tier2: FAIL
  INCOMPLETE
  ✓ plugin/terminal_jail/rules/packs/db.yaml constrains the pack-db-drop-database and pack-db-drop-table block rules to a SQL execution context: each is a composite/and rule requiring a SQL client token plus the statement in execution position: PASS: db.yaml pack-db-drop-database (line ~85) and pack-db-drop-table (~110) both use match.type=composite, operator=and, with condition 1 = SQL client token regex (psql|mysql|mariadb|sqlite3|mysqladmin|sqlplus) and condition 2 = execution-position regex (-c/-e/--command/--execute arms A/B1/B2/C).
  ✓ Through intercept() with the pack installed, psql -c DROP DATABASE, psql -c DROP TABLE and mysql -e DROP TABLE each return action block with the matching pack-db-drop-* rule id: PASS: live intercept() with pack installed: psql -c "DROP DATABASE prod" -> block/pack-db-drop-database; psql -c "DROP TABLE users" -> block/pack-db-drop-table; mysql -e "DROP TABLE users;" -> block/pack-db-drop-table.
  ✓ Through intercept() with the pack installed, the four documented false-positive shapes (sed -i substitution text, git commit -m message text, a read-only SELECT whose quoted literal merely contains the phrase, and echo redirecting the phrase to a file) return no pack-db-* attribution: PASS: live intercept() with pack installed: sed -i substitution -> allow/None; git commit -am -> allow/None; psql -c SELECT with quoted literal 'drop database retry' -> allow/None; echo "DROP TABLE users" > file -> allow/allow-echo. No pack-db-* attribution on any.
  ✗ plugin/test_rule_packs.py carries a regression class exercising the block and allow shapes with the installed-pack fixture, and the full suite passes with only the new tests added (zero regressions): Not verified — evaluation terminated before this criterion was checked
  ✗ CHANGELOG.md and the pack header document the accepted residuals: the -f file body remains DF-TERMINAL-JAIL-10, and destructive SQL pasted into a non-SQL-client interpreter is no longer caught: Not verified — evaluation terminated before this criterion was checked
Partial verdict — evaluation hit resource cap before all criteria verified

Overall: FAIL ✗
