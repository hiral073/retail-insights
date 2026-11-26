import io
import json
import shutil
import sqlite3
from contextlib import closing

import pytest

from checks import run_checks
from load_data import SCHEMA
from views import SQL_DIR, apply_views

EXCLUDED_CODES = [
    "POST", "DOT", "M", "D", "S", "B", "BANK CHARGES", "ADJUST", "ADJUST2",
    "AMAZONFEE", "CRUK", "PADS", "TEST001", "TEST002",
]


def line(invoice="1", stock_code="85048", quantity=10, price=10.0, customer_id=1):
    return (
        invoice, stock_code, "LIGHTS", quantity, "2011-01-01 09:00:00", price,
        customer_id, "France", int(invoice.startswith("C")), int(customer_id is None),
    )


def make_db(path, lines):
    with closing(sqlite3.connect(path)) as con, con:
        con.execute(SCHEMA)
        con.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", lines)
    return path


def sql_folder(tmp_path, view_body=None):
    folder = tmp_path / "sql"
    folder.mkdir()
    if view_body is None:
        shutil.copy(SQL_DIR / "01_clean_sales.sql", folder)
    else:
        (folder / "01_clean_sales.sql").write_text(
            f"DROP VIEW IF EXISTS clean_sales; CREATE VIEW clean_sales AS {view_body};",
            encoding="utf-8",
        )
    return folder


def run(database, folder, rows, revenue):
    out, err = io.StringIO(), io.StringIO()
    code = run_checks.run(database, folder, rows, revenue, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def statuses(output):
    return [text.split()[0] for text in output.splitlines() if text[:4] in ("PASS", "FAIL")]


def test_view_keeps_only_clean_product_sales(tmp_path):
    db = make_db(tmp_path / "r.db", [
        line("1"),
        line("2", customer_id=None),
        line("C3"),
        line("4", quantity=0),
        line("5", quantity=-1),
        line("6", price=0),
        line("7", price=-5.0),
        line("8", stock_code="m"),
        *[line("9", stock_code=code) for code in EXCLUDED_CODES],
        line("10", stock_code="15056BL"),
    ])
    apply_views(db)

    with closing(sqlite3.connect(db)) as con:
        invoices = con.execute("SELECT invoice FROM clean_sales ORDER BY CAST(invoice AS INTEGER)").fetchall()

    assert invoices == [("1",), ("2",), ("10",)]


def test_all_checks_pass(tmp_path):
    db = make_db(tmp_path / "r.db", [line("1"), line("C2")])

    code, out, err = run(db, sql_folder(tmp_path), rows=2, revenue=100.0)

    assert (code, statuses(out), err) == (0, ["PASS"] * 4, "")


@pytest.mark.parametrize("view_body, bad_line", [
    ("SELECT * FROM sales", line("C2", quantity=1, price=0.01)),
    ("SELECT * FROM sales", line("2", quantity=0)),
    ("SELECT * FROM sales", line("2", price=0)),
])
def test_dirty_rows_in_view_fail_with_exit_code_2(tmp_path, view_body, bad_line):
    db = make_db(tmp_path / "r.db", [line("1"), bad_line])

    code, out, err = run(db, sql_folder(tmp_path, view_body), rows=2, revenue=100.0)

    assert code == 2
    assert statuses(out).count("FAIL") == 1
    assert "1 found" in err


def test_wrong_row_count_fails(tmp_path):
    db = make_db(tmp_path / "r.db", [line("1")])

    code, _, err = run(db, sql_folder(tmp_path), rows=2, revenue=100.0)

    assert code == 2
    assert "FAIL  sales row count: 1 (expected 2)" in err


@pytest.mark.parametrize("revenue, expected_code", [
    (100.4, 0), (99.6, 0), (100.6, 2), (99.4, 2),
])
def test_revenue_tolerance_is_half_a_percent(tmp_path, revenue, expected_code):
    db = make_db(tmp_path / "r.db", [line("1")])

    code, _, _ = run(db, sql_folder(tmp_path), rows=1, revenue=revenue)

    assert code == expected_code


@pytest.mark.parametrize("view_body", ["SELECT nonsense FROM sales", "SELECT FROM"])
def test_broken_sql_fails_and_names_the_file(tmp_path, view_body):
    db = make_db(tmp_path / "r.db", [line("1")])

    code, out, err = run(db, sql_folder(tmp_path, view_body), rows=1, revenue=100.0)

    assert code == 2
    assert "01_clean_sales.sql" in err
    assert statuses(out) == ["FAIL", "PASS", "FAIL", "FAIL", "FAIL"]


def test_checks_use_sql_files_not_a_stale_view_and_leave_database_alone(tmp_path):
    db = make_db(tmp_path / "r.db", [line("1")])
    apply_views(db)
    empty = tmp_path / "empty"
    empty.mkdir()
    before = db.read_bytes()

    code, _, _ = run(db, empty, rows=1, revenue=100.0)

    assert code == 2
    assert db.read_bytes() == before


def test_missing_database_fails_without_creating_it(tmp_path):
    code, _, err = run(tmp_path / "none.db", sql_folder(tmp_path), rows=1, revenue=1.0)

    assert code == 2
    assert "none.db" in err
    assert not (tmp_path / "none.db").exists()


@pytest.mark.parametrize("relative, triggers", [
    ("sql/01_clean_sales.sql", True),
    ("sql/reports/monthly.SQL", True),
    ("sql/notes.md", False),
    ("other/query.sql", False),
    ("load_data.py", False),
])
def test_hook_only_triggers_for_sql_files_in_sql_folder(relative, triggers):
    payload = {"tool_input": {"file_path": str(run_checks.ROOT / relative)}}

    assert run_checks.is_project_sql(payload) is triggers


def test_hook_mode_skips_unrelated_files(monkeypatch, capsys):
    payload = {"tool_input": {"file_path": str(run_checks.ROOT / "README.md")}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert run_checks.main(["--hook"]) == 0
    assert capsys.readouterr().out == ""
