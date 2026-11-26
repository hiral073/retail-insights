"""Rebuild the views on a temporary copy of retail.db and check the data.

Usage:
    python checks/run_checks.py          # run the checks
    python checks/run_checks.py --hook   # Claude Code PostToolUse hook: read the
                                         # tool call from stdin and run only if it
                                         # touched a .sql file in sql/

Exit code 0 means every check passed (or the hook had nothing to do).
Exit code 2 means a check failed; the reason is written to stderr.
"""

import argparse
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from views import SQL_DIR, apply_views  # noqa: E402

DATABASE = ROOT / "retail.db"
EXPECTED_ROWS = 1_044_848
EXPECTED_REVENUE = 19_700_000  # GBP
REVENUE_TOLERANCE = 0.005
FAILED = 2


def is_project_sql(payload):
    """True if the hook payload is for a .sql file inside the sql folder."""
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return False
    path = Path(file_path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    return path.suffix.lower() == ".sql" and path.is_relative_to(SQL_DIR)


def _copy_database(source, target):
    uri = Path(source).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as original:
        with closing(sqlite3.connect(target)) as copy:
            original.backup(copy)


def _drop_views(database):
    """Remove existing views so that only the current SQL files are tested."""
    with closing(sqlite3.connect(database)) as con, con:
        names = con.execute("SELECT name FROM sqlite_master WHERE type = 'view'")
        for (name,) in names.fetchall():
            quoted = name.replace('"', '""')
            con.execute(f'DROP VIEW "{quoted}"')


def _check_row_count(con, expected_rows):
    rows = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    return rows == expected_rows, f"{rows:,} (expected {expected_rows:,})"


def _check_no_rows(con, condition):
    found = con.execute(f"SELECT COUNT(*) FROM clean_sales WHERE {condition}").fetchone()[0]
    return found == 0, f"{found:,} found"


def _check_revenue(con, expected_revenue):
    revenue = con.execute(
        "SELECT TOTAL(quantity * price) FROM clean_sales"
    ).fetchone()[0]
    difference = abs(revenue - expected_revenue) / expected_revenue
    return difference <= REVENUE_TOLERANCE, (
        f"GBP {revenue:,.2f} differs by {difference:.2%} from GBP {expected_revenue:,.0f} "
        f"(limit {REVENUE_TOLERANCE:.2%})"
    )


def _results(database, sql_dir, expected_rows, expected_revenue):
    """Yield (passed, name, detail) for each check, using a temporary copy."""
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "retail_check.db"
        _copy_database(database, copy)
        try:
            _drop_views(copy)
            apply_views(copy, sql_dir)
        except (RuntimeError, sqlite3.Error, OSError) as error:
            yield False, "rebuild views", str(error)

        checks = [
            ("sales row count", lambda con: _check_row_count(con, expected_rows)),
            ("clean_sales has no cancelled invoices",
             lambda con: _check_no_rows(con, "invoice LIKE 'C%'")),
            ("clean_sales has no quantity or price of zero or less",
             lambda con: _check_no_rows(
                 con, "quantity IS NULL OR quantity <= 0 OR price IS NULL OR price <= 0")),
            ("clean_sales revenue", lambda con: _check_revenue(con, expected_revenue)),
        ]
        with closing(sqlite3.connect(copy)) as con:
            for name, check in checks:
                try:
                    passed, detail = check(con)
                except sqlite3.Error as error:
                    passed, detail = False, f"could not run: {error}"
                yield passed, name, detail


def run(database=DATABASE, sql_dir=SQL_DIR, expected_rows=EXPECTED_ROWS,
        expected_revenue=EXPECTED_REVENUE, out=None, err=None):
    """Print each check as PASS or FAIL and return the exit code."""
    out = out or sys.stdout
    err = err or sys.stderr
    failures = []
    try:
        for passed, name, detail in _results(database, sql_dir, expected_rows, expected_revenue):
            text = f"{'PASS' if passed else 'FAIL'}  {name}: {detail}"
            print(text, file=out)
            if not passed:
                failures.append(text)
    except (sqlite3.Error, OSError) as error:
        failures.append(f"FAIL  could not copy {database}: {error}")
        print(failures[-1], file=out)

    if failures:
        print(f"Data checks failed ({len(failures)}):", *failures, sep="\n", file=err)
        return FAILED
    print("All checks passed.", file=out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hook", action="store_true",
                        help="read a Claude Code tool call from stdin")
    if parser.parse_args(argv).hook:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as error:
            print(f"Data checks failed: unreadable hook input: {error}", file=sys.stderr)
            return FAILED
        if not is_project_sql(payload):
            return 0
    return run()


if __name__ == "__main__":
    sys.exit(main())
