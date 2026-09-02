#!/data/data/com.termux/files/usr/bin/sh
set -e
cd "$(dirname "$0")"
python tests/test_preserve.py
python tests/test_fixtures.py
python tests/test_json.py
python tests/test_cli.py
python tests/test_db_frozen.py
echo ALL_PASS
