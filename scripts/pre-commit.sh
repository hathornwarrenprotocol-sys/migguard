#!/data/data/com.termux/files/usr/bin/sh
set -e
cd "$(dirname "$0")/.."
python3 migguard.py check --changed-since HEAD --db ./real/dev.db --root . || true
sh run_tests.sh
