#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "real" / "dev.db"
SQL = ROOT / "fixtures" / "sql" / "add_index.sql"
NEED_MIG = {"score", "verdict", "files", "findings", "dry_run"}
NEED_DRY = {"applied", "error", "rows_lost"}
NEED_PRES = {"verdict", "before_sha256", "after_sha256", "sql"}


def main():
    mig = subprocess.run(
        [sys.executable, str(ROOT / "migguard.py"), str(SQL), "--db", str(DB), "--json"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert mig.returncode == 0, mig.stderr
    payload = json.loads(mig.stdout)
    missing = NEED_MIG - set(payload)
    assert not missing, missing
    assert set(NEED_DRY) <= set(payload["dry_run"])
    print("migguard json keys ok", payload["verdict"], payload["score"])

    pres = subprocess.run(
        [
            sys.executable, str(ROOT / "preserve.py"), "--json",
            "--db", str(DB),
            "--sql", str(ROOT / "real/prisma/migrations/20240320000000_rename_biography_fixed/migration.sql"),
            "--table", "Profile", "--key", "userId",
            "--from-col", "biograpy", "--to-col", "biography",
        ],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert pres.returncode == 0, pres.stderr
    p2 = json.loads(pres.stdout)
    missing = NEED_PRES - set(p2)
    assert not missing, missing
    print("preserve json keys ok", p2["verdict"])
    print("PASS json")


if __name__ == "__main__":
    raise SystemExit(main())
