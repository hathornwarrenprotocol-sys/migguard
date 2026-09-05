#!/usr/bin/env python3
"""preserve — did this SQL keep the values in a column?"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

TOOL_VERSION = "0.4.0"


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def statements(sql: str) -> list[str]:
    sql = re.sub(r"--.*?$", "", sql, flags=re.M)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return [s.strip() for s in sql.split(";") if s.strip()]


def schema_fingerprint(db: Path) -> str:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT name, type, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
        ).fetchall()
        return json.dumps(rows)
    finally:
        conn.close()


def column_map(db: Path, table: str, key: str, col: str) -> dict[str, str] | None:
    conn = sqlite3.connect(db)
    try:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({qident(table)})")}
        if col not in cols or key not in cols:
            return None
        rows = conn.execute(
            f"SELECT {qident(key)}, {qident(col)} FROM {qident(table)} ORDER BY {qident(key)}"
        ).fetchall()
        return {str(k): "" if v is None else str(v) for k, v in rows}
    finally:
        conn.close()


def digest(mapping: dict[str, str] | None) -> str | None:
    if mapping is None:
        return None
    blob = json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_on_clone(src: Path, sql: str) -> tuple[Path, str | None, bool]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dest = Path(tmp.name)
    shutil.copy2(src, dest)
    before = schema_fingerprint(dest)

    conn = sqlite3.connect(dest)
    err = None
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")
        try:
            for stmt in statements(sql):
                conn.execute(stmt)
            conn.commit()
        except sqlite3.Error as e:
            err = str(e)
            conn.rollback()
    finally:
        conn.close()

    after = schema_fingerprint(dest)
    partial = bool(err) and after != before
    return dest, err, partial


def classify(before, after_new, err, partial) -> str:
    if partial:
        return "PARTIAL"
    if err:
        return "APPLY_FAILED"
    if before is None:
        return "NO_SOURCE_COLUMN"
    if after_new is None:
        return "DESTROYED"
    if before == after_new:
        return "PRESERVED"
    return "DESTROYED"


def main() -> int:
    p = argparse.ArgumentParser(prog="preserve")
    p.add_argument("--version", action="version", version="preserve " + TOOL_VERSION)
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--sql", required=True, type=Path)
    p.add_argument("--table", required=True)
    p.add_argument("--key", default="userId")
    p.add_argument("--from-col", required=True)
    p.add_argument("--to-col", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    before = column_map(args.db, args.table, args.key, args.from_col)
    clone, err, partial = apply_on_clone(args.db, args.sql.read_text(encoding="utf-8"))
    try:
        after_new = column_map(clone, args.table, args.key, args.to_col)
        after_old = column_map(clone, args.table, args.key, args.from_col)
    finally:
        clone.unlink(missing_ok=True)

    result = classify(before, after_new, err, partial)
    payload = {
        "tool": "preserve",
        "tool_version": TOOL_VERSION,
        "engine": "sqlite",
        "engine_version": sqlite3.sqlite_version,
        "db_sha256": file_sha256(args.db),
        "sql": str(args.sql),
        "sql_sha256": file_sha256(args.sql),
        "verdict": result,
        "error": err,
        "partial": partial,
        "before_sha256": digest(before),
        "after_sha256": digest(after_new),
        "from_col_still_present": after_old is not None,
        "before": before,
        "after": after_new,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("preserve — value identity")
        print("=" * 40)
        print(f"tool: preserve {TOOL_VERSION}  sqlite {sqlite3.sqlite_version}")
        print(f"sql: {args.sql}")
        print(f"verdict: {result}")
        print(f"partial: {partial}")
        if err:
            print(f"error: {err}")
        print(f"before sha256={payload['before_sha256']}")
        print(f"after  sha256={payload['after_sha256']}")
        print(f"old column still present: {payload['from_col_still_present']}")
        print("source database was never modified.")
    return 0 if result == "PRESERVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
