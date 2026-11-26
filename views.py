"""Create the project's views from the scripts in sql/."""

import sqlite3
from contextlib import closing
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"


def apply_views(database, sql_dir=SQL_DIR):
    """Run every .sql file under `sql_dir` against `database`, in path order."""
    scripts = sorted(
        path for path in Path(sql_dir).rglob("*") if path.suffix.lower() == ".sql"
    )
    with closing(sqlite3.connect(database)) as con:
        for script in scripts:
            try:
                con.executescript(script.read_text(encoding="utf-8-sig"))
                con.commit()
                _validate_views(con)
            except (sqlite3.Error, UnicodeError) as error:
                raise RuntimeError(f"{script.name}: {error}") from error


def _validate_views(con):
    """SQLite accepts some broken views at creation, so query each one."""
    names = con.execute("SELECT name FROM sqlite_master WHERE type = 'view'").fetchall()
    for (name,) in names:
        quoted = name.replace('"', '""')
        con.execute(f'SELECT * FROM "{quoted}" LIMIT 0')
