# migguard 0.4.0

SQLite migration lint, sandbox dry-run, and value-preservation check.
Never writes the source database.

## Install

    git clone https://github.com/hathornwarrenprotocol-sys/migguard.git
    cd migguard
    python3 -m pip install -e .
    migguard --version

Python 3.10+. Without install: python3 migguard.py

## Commands

    migguard check --db ./real/dev.db --code-root ./app_sample
    migguard check fixtures/sql/add_index.sql --db ./real/dev.db
    migguard check fixtures/sql/rename_column.sql --db ./real/dev.db
    migguard check fixtures/sql/drop_table.sql --db ./real/dev.db --code-root ./app_sample
    python3 preserve.py --db ./real/dev.db --sql path.sql --table Profile --key userId --from-col old --to-col new --json
    sh run_tests.sh

check is dry-run by default.

## Exit codes

0  ALL_PASS or PRESERVED
1  APPLY_FAILED or blocked
2  missing files or not SQL

SQLite only.

    migguard query --db ./real/dev.db --code-root ./app_sample

More: https://hathornwarren.com
