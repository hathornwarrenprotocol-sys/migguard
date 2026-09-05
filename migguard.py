#!/usr/bin/env python3
"""migguard — local schema migration safety guard."""

from __future__ import annotations

TOOL_VERSION = "0.4.0"

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DESTRUCTIVE_PATTERNS = [
    (r"\bDROP\s+TABLE\b", "DROP TABLE", 40, "Removes table and all rows"),
    (r"\bDROP\s+COLUMN\b", "DROP COLUMN", 25, "Permanently deletes column data"),
    (r"\bDROP\s+INDEX\b", "DROP INDEX", 8, "Can change query plans / uniqueness"),
    (r"\bTRUNCATE\b", "TRUNCATE", 40, "Deletes all rows"),
    (r"\bDELETE\s+FROM\b", "DELETE", 8, "Deletes rows"),
    (r"\bALTER\s+TABLE\b.+\bRENAME\b", "RENAME", 12, "Breaks queries and ORMs that still use old names"),
    (r"\bALTER\s+TABLE\b.+\bALTER\s+COLUMN\b", "ALTER COLUMN", 15, "Type/nullability change can fail or coerce data"),
    (r"\bALTER\s+TABLE\b.+\bNOT\s+NULL\b", "NOT NULL", 10, "Fails if existing rows have NULLs and no DEFAULT"),
    (r"\bDROP\s+VIEW\b", "DROP VIEW", 8, "Removes a view dependents may use"),
]

MIG_GLOBS = (
    "prisma/migrations/**/migration.sql",
    "supabase/migrations/*.sql",
    "migrations/*.sql",
    "db/migrations/*.sql",
    "sql/migrations/*.sql",
)

CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".prisma"}


def strip_comments(sql: str) -> str:
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def split_statements(sql: str) -> list[str]:
    return [p.strip() for p in strip_comments(sql).split(";") if p.strip()]


@dataclass
class Finding:
    kind: str
    severity: int
    detail: str
    excerpt: str
    suggestion: str | None = None


def suggest(kind: str) -> str | None:
    return {
        "DROP TABLE": "Prefer rename + stop writes, copy data, then drop in a later release.",
        "DROP COLUMN": "Ship code that stops reading the column first (expand/contract).",
        "ADD NOT NULL without DEFAULT": "ADD nullable, backfill, then SET NOT NULL.",
        "NOT NULL": "Backfill existing NULLs or provide a DEFAULT before enforcing.",
        "RENAME": "Add the new name, dual-write, then drop the old name.",
        "DELETE": "Require a WHERE you can replay; take a row count first.",
        "TRUNCATE": "Avoid in app migrations; use a targeted DELETE if you must.",
        "DELETE without WHERE": "Require a WHERE you can replay; take a row count first.",
    }.get(kind)


def lint_sql(sql: str) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in split_statements(sql):
        excerpt = stmt[:140].replace("\n", " ")
        for pat, kind, sev, detail in DESTRUCTIVE_PATTERNS:
            if not re.search(pat, stmt, flags=re.IGNORECASE | re.DOTALL):
                continue
            if kind == "DELETE" and re.search(r"\bWHERE\b", stmt, re.I):
                findings.append(
                    Finding("DELETE with WHERE", 8, "Row deletion — confirm the filter", excerpt, suggest("DELETE"))
                )
            elif kind == "DELETE":
                findings.append(
                    Finding("DELETE without WHERE", 35, "May wipe a table", excerpt, suggest("DELETE without WHERE"))
                )
            else:
                findings.append(Finding(kind, sev, detail, excerpt, suggest(kind)))
        if re.search(r"\bADD\s+COLUMN\b.+\bNOT\s+NULL\b", stmt, re.I | re.DOTALL) and not re.search(
            r"\bDEFAULT\b", stmt, re.I
        ):
            findings.append(
                Finding(
                    "ADD NOT NULL without DEFAULT",
                    22,
                    "Existing rows cannot satisfy NOT NULL",
                    excerpt,
                    suggest("ADD NOT NULL without DEFAULT"),
                )
            )
    return findings


def sql_names(sql: str) -> set[str]:
    names: set[str] = set()
    for stmt in split_statements(sql):
        for pat in (
            r'\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?["`[]?(\w+)',
            r'\bDROP\s+COLUMN\s+["`[]?(\w+)',
            r'\bRENAME\s+(?:COLUMN\s+)?["`[]?(\w+)',
            r'\bTO\s+["`[]?(\w+)',
            r'\bFROM\s+["`[]?(\w+)',
            r'\bTABLE\s+["`[]?(\w+)',
        ):
            for m in re.finditer(pat, stmt, flags=re.I):
                names.add(m.group(1))
    return names


def scan_code_root(code_root: Path, names: set[str]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if not code_root.exists() or not names:
        return hits
    for path in sorted(code_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in CODE_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name in sorted(names):
            if re.search(rf"\b{re.escape(name)}\b", text):
                hits.append((name, str(path)))
    return hits


def table_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    out: dict[str, int] = {}
    for (name,) in cur.fetchall():
        try:
            out[name] = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        except sqlite3.Error:
            out[name] = -1
    return out


@dataclass
class DryRunResult:
    applied: bool
    error: str | None
    tables_before: dict[str, int]
    tables_after: dict[str, int]
    rows_lost: int
    tables_dropped: list[str]
    tables_added: list[str]


def dry_run(source_db: Path | None, migration_sql: str, seed_sql: str | None = None) -> DryRunResult:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dest = Path(tmp.name)
    try:
        if source_db and source_db.exists():
            shutil.copy2(source_db, dest)
        conn = sqlite3.connect(dest)
        conn.execute("PRAGMA foreign_keys = ON")
        if seed_sql and not (source_db and source_db.exists()):
            conn.executescript(seed_sql)
            conn.commit()
        before = table_row_counts(conn)
        err = None
        applied = False
        try:
            conn.executescript(migration_sql)
            conn.commit()
            applied = True
        except sqlite3.Error as e:
            err = str(e)
            conn.rollback()
        after = table_row_counts(conn) if applied else dict(before)
        conn.close()
        dropped = sorted(set(before) - set(after))
        added = sorted(set(after) - set(before))
        lost = 0
        for t, n in before.items():
            if t not in after:
                lost += max(n, 0)
            elif after[t] >= 0 and n >= 0 and after[t] < n:
                lost += n - after[t]
        return DryRunResult(applied, err, before, after, lost, dropped, added)
    finally:
        dest.unlink(missing_ok=True)


def safety_score(findings: list[Finding], dry: DryRunResult | None) -> int:
    score = 100
    seen: set[str] = set()
    for f in findings:
        if f.kind in seen:
            score -= max(4, f.severity // 4)
        else:
            score -= f.severity
            seen.add(f.kind)
    if dry:
        if dry.error:
            score -= 30
        score -= min(40, dry.rows_lost * 2)
        score -= 15 * len(dry.tables_dropped)
    return max(0, min(100, score))


def verdict(score: int) -> str:
    if score >= 85:
        return "SAFE"
    if score >= 60:
        return "CAUTION"
    if score >= 35:
        return "RISKY"
    return "BLOCK"


def discover(root: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in MIG_GLOBS:
        found.extend(sorted(root.glob(pattern)))
    uniq: list[Path] = []
    seen: set[Path] = set()
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def looks_like_migration(path: Path) -> bool:
    name = path.as_posix().lower()
    if path.suffix.lower() != ".sql":
        return False
    return any(
        token in name
        for token in (
            "/prisma/migrations/",
            "/supabase/migrations/",
            "/migrations/",
            "/db/migrations/",
            "/sql/migrations/",
        )
    ) or path.name == "migration.sql"


def changed_since(root: Path, ref: str) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=ACMR", f"{ref}...HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"git not found ({exc})") from exc
    if proc.returncode != 0:
        proc = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=ACMR", ref],
            check=False,
            capture_output=True,
            text=True,
        )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"git diff failed for {ref}")
    out: list[Path] = []
    seen: set[Path] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = (root / line).resolve() if not Path(line).is_absolute() else Path(line)
        if not p.exists():
            repo = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            if repo.returncode == 0:
                p = Path(repo.stdout.strip()) / line
        if p.exists() and looks_like_migration(p) and p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    return sorted(out)


def load_sql(paths: Iterable[Path]) -> str:
    return "\n;\n".join(f"-- file: {p}\n{p.read_text(encoding='utf-8')}" for p in paths)


def format_report(
    files: list[Path],
    findings: list[Finding],
    dry: DryRunResult | None,
    score: int,
    code_hits: list[tuple[str, str]] | None = None,
) -> str:
    lines = [
        "migguard — migration safety report",
        "=" * 40,
        f"files: {', '.join(str(p) for p in files) or '(none)'}",
        f"score: {score}/100   verdict: {verdict(score)}",
        "",
    ]
    if findings:
        lines.append("static findings:")
        for f in findings:
            lines.append(f"  - [{f.severity:>2}] {f.kind}: {f.detail}")
            lines.append(f"        {f.excerpt}")
            if f.suggestion:
                lines.append(f"        fix: {f.suggestion}")
    else:
        lines.append("static findings: none")
    if dry:
        lines.append("")
        lines.append("sandbox dry-run:")
        lines.append(f"  APPLY FAILED: {dry.error}" if dry.error else "  applied: yes")
        lines.append(f"  rows_lost: {dry.rows_lost}")
        if dry.tables_dropped:
            lines.append(f"  tables_dropped: {', '.join(dry.tables_dropped)}")
        if dry.tables_added:
            lines.append(f"  tables_added: {', '.join(dry.tables_added)}")
        lines.append("  row counts before → after:")
        for t in sorted(set(dry.tables_before) | set(dry.tables_after)):
            b = dry.tables_before.get(t, 0)
            a = dry.tables_after.get(t, "—")
            mark = "  "
            if t not in dry.tables_after:
                mark = "✗ "
            elif t not in dry.tables_before:
                mark = "+ "
            elif isinstance(a, int) and a < b:
                mark = "↓ "
            lines.append(f"    {mark}{t}: {b} → {a}")
    if code_hits:
        lines.append("")
        lines.append("code-root references:")
        for name, path in code_hits:
            lines.append(f"  {name} → {path}")
    lines.append("")
    lines.append("source database was never modified.")
    return "\n".join(lines)



def drift_report(a: Path, b: Path) -> tuple[str, int]:
    def counts(path: Path) -> dict[str, int]:
        conn = sqlite3.connect(path)
        try:
            return table_row_counts(conn)
        finally:
            conn.close()
    ca, cb = counts(a), counts(b)
    names = sorted(set(ca) | set(cb))
    diffs = []
    for n in names:
        if n not in ca:
            diffs.append(n + " only in other")
        elif n not in cb:
            diffs.append(n + " only in db")
        elif ca[n] != cb[n]:
            diffs.append("%s %s != %s" % (n, ca[n], cb[n]))
    if diffs:
        print("migguard drift")
        for d in diffs:
            print(" ", d)
        print("APPLY_FAILED")
        return "APPLY_FAILED", 1
    print("migguard drift")
    print("tables", len(ca))
    print("ALL_PASS")
    return "ALL_PASS", 0

def parse_argv(argv: list[str] | None) -> tuple[bool, argparse.Namespace]:
    raw = list(sys.argv[1:] if argv is None else argv)
    check_mode = False
    query_mode = False
    drift_mode = False
    if raw and raw[0] == "check":
        check_mode = True
        raw = raw[1:]
    elif raw and raw[0] == "query":
        query_mode = True
        raw = raw[1:]
    elif raw and raw[0] == "drift":
        drift_mode = True
        raw = raw[1:]
    p = argparse.ArgumentParser(prog="migguard", description="Lint + sandbox dry-run SQL migrations")
    p.add_argument("--version", action="version", version="migguard " + TOOL_VERSION)
    p.add_argument("migrations", nargs="*", type=Path, help="SQL files (optional if --discover / --changed-since)")
    p.add_argument("--discover", action="store_true", help="Find prisma/supabase/migrations folders")
    p.add_argument("--changed-since", metavar="REF", help="Only SQL migrations changed since this git ref")
    p.add_argument("--root", type=Path, default=Path("."), help="Project root for discover / git")
    p.add_argument("--db", type=Path, default=None, help="SQLite DB to clone (never modified)")
    p.add_argument("--seed", type=Path, default=None, help="Seed SQL if no --db")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fail-under", type=int, default=60)
    p.add_argument("--max-row-loss", type=int, default=None)
    p.add_argument("--no-dry-run", action="store_true")
    p.add_argument("--apply", action="store_true", help="Alias of --no-dry-run (check subcommand)")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--code-root", type=Path, default=None, help="Scan code for dropped names")
    p.add_argument("--other", type=Path, default=None, help="drift: second sqlite file")
    p.add_argument("--table", default=None, help="preserve: table name")
    p.add_argument("--key", default="userId", help="preserve: key column")
    p.add_argument("--from-col", default=None, dest="from_col", help="preserve: source column")
    p.add_argument("--to-col", default=None, dest="to_col", help="preserve: target column")

    args = p.parse_args(raw)
    if args.apply:
        args.no_dry_run = True
    return check_mode, query_mode, drift_mode, args


def main(argv: list[str] | None = None) -> int:
    check_mode, query_mode, drift_mode, args = parse_argv(argv)


    if drift_mode:
        if args.db is None or args.other is None:
            print("drift needs --db and --other", file=sys.stderr)
            return 2
        _tok, code = drift_report(args.db, args.other)
        return code
    if query_mode:
        if args.db is None or args.code_root is None:
            print("query needs --db and --code-root", file=sys.stderr)
            return 2
        conn = sqlite3.connect(args.db)
        try:
            qnames = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
        finally:
            conn.close()
        qhits = scan_code_root(args.code_root, qnames)
        if not args.json:
            print("migguard query")
            print("tables:", ", ".join(sorted(qnames)))
            for name, path in qhits:
                print(f"  {name} -> {path}")
            print("ALL_PASS" if qhits else "APPLY_FAILED")
        else:
            print(json.dumps({"tables": sorted(qnames), "code_hits": [{"name": n, "path": p} for n, p in qhits]}, indent=2))
        return 0 if qhits else 1

    root = args.root.resolve()
    files = list(args.migrations)
    if args.discover:
        files.extend(discover(root))
    if args.changed_since:
        files.extend(changed_since(root, args.changed_since))

    dedup: list[Path] = []
    seen: set[Path] = set()
    for f in files:
        rp = f.resolve() if f.exists() else f
        if rp not in seen:
            seen.add(rp)
            dedup.append(f)
    files = dedup

    not_sql = [str(m) for m in files if m.suffix.lower() != ".sql"]
    if not_sql:
        print("not sql: " + ", ".join(not_sql), file=sys.stderr)
        return 2

    missing = [str(m) for m in files if not m.exists()]
    if missing:
        print(f"missing files: {', '.join(missing)}", file=sys.stderr)
        return 2
    if not files:
        msg = "no migration files"
        if args.changed_since:
            msg += f" changed since {args.changed_since}"
        else:
            msg += " (pass paths, --discover, or --changed-since)"
        print(msg, file=sys.stderr)
        return 2

    sql = load_sql(files)
    findings = lint_sql(sql)
    dry = None
    if not args.no_dry_run:
        seed = args.seed.read_text(encoding="utf-8") if args.seed else None
        dry = dry_run(args.db, sql, seed)
    score = safety_score(findings, dry)

    names = sql_names(sql)
    if dry:
        names |= set(dry.tables_dropped) | set(dry.tables_added)
    code_hits = scan_code_root(args.code_root, names) if args.code_root else []

    if args.quiet and not args.json:
        print(f"{score} {verdict(score)}")
        if args.max_row_loss is not None and dry and dry.rows_lost > args.max_row_loss:
            rc = 1
        else:
            rc = 1 if score < args.fail_under else 0
    elif args.json:
        payload = {
            "score": score,
            "verdict": verdict(score),
            "files": [str(f) for f in files],
            "findings": [asdict(f) for f in findings],
            "dry_run": asdict(dry) if dry else None,
            "code_hits": [{"name": n, "path": p} for n, p in code_hits],
        }
        print(json.dumps(payload, indent=2))
        if args.max_row_loss is not None and dry and dry.rows_lost > args.max_row_loss:
            rc = 1
        else:
            rc = 1 if score < args.fail_under else 0
    else:
        print(format_report(files, findings, dry, score, code_hits))
        if args.max_row_loss is not None and dry and dry.rows_lost > args.max_row_loss:
            rc = 1
        else:
            rc = 1 if score < args.fail_under else 0

    if check_mode:
        if args.table and args.from_col and args.to_col:
            if args.db is None or not files:
                print("preserve check needs --db and a sql file", file=sys.stderr)
                return 2
            from preserve import apply_on_clone, column_map, classify
            before = column_map(args.db, args.table, args.key, args.from_col)
            clone, perr, partial = apply_on_clone(args.db, sql)
            try:
                after_new = column_map(clone, args.table, args.key, args.to_col)
            finally:
                clone.unlink(missing_ok=True)
            pverdict = classify(before, after_new, perr, partial)
            print("preserve", pverdict)
            if pverdict == "PRESERVED":
                print("PRESERVED")
                return 0
            print("APPLY_FAILED")
            return 1
        if dry and dry.error:
            print("APPLY_FAILED")
            return 1
        if any(f.kind == "RENAME" for f in findings) and dry and dry.applied and not dry.error:
            print("PRESERVED")
            return 0
        if rc == 0:
            print("ALL_PASS")
            return 0
        print("APPLY_FAILED")
        return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
