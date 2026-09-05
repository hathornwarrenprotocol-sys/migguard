# Changelog

## 0.4.0
- check first-token; PRESERVED / ALL_PASS / APPLY_FAILED
- query --db --code-root
- check --table --key --from-col --to-col uses preserve.py
- drift --db --other
- scripts/pre-commit.sh
- pip script entry migguard = migguard:main

# Changelog

## 0.3.0
- --version, --quiet
- reject non-sql
- create_table + rename_column fixtures
- source db frozen test

# Changelog

## 0.2.2
- preserve applies statements in one transaction (no executescript)
- PARTIAL only if schema changed after an error
- fixture expectations in JSON
- GitHub Action, LICENSE, gitignore

## 0.2.0
- preserve value-hash on Prisma rename vs DROP+ADD
- migguard sandbox scores on SQLite clone

## 0.1.0
- lint + dry-run demo
