# migguard

SQLite migration check. Clone the database, lint the SQL, dry-run in a sandbox,
print one token. Never writes the source file.

Install

    git clone https://github.com/hathornwarrenprotocol-sys/migguard.git
    cd migguard
    python3 -m pip install -e .
    migguard --version

Commands

    migguard check file.sql --db ./real/dev.db
    migguard check file.sql --db ./real/dev.db --table User --key id --from-col name --to-col fullName
    migguard query --db ./real/dev.db --code-root ./app_sample
    sh run_tests.sh

Tokens: ALL_PASS  PRESERVED  APPLY_FAILED
Exit: 0 pass, 1 blocked, 2 bad input

Repo: https://github.com/hathornwarrenprotocol-sys/migguard
