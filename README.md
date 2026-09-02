# migguard 0.2.2

SQLite migration lint, sandbox dry-run, and value-preservation check.
Never writes the source database.

## Commands

python migguard.py path.sql --db ./real/dev.db --max-row-loss 0 --fail-under 60
python migguard.py path.sql --db ./real/dev.db --json
python preserve.py --db ./real/dev.db --sql path.sql --table Profile --key userId --from-col old --to-col new --json
sh run_tests.sh

## Exit codes

0  SAFE enough (score >= --fail-under and row loss <= cap)
1  blocked
2  missing files / bad args

## preserve verdicts

PRESERVED     values moved; sha256 unchanged
DESTROYED     finished; values missing or different
APPLY_FAILED  error; schema unchanged after rollback
PARTIAL       error; schema already changed

SQLite only.
