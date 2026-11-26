import sqlite3
from contextlib import closing
from datetime import datetime

import openpyxl
import pytest

from load_data import build_database, summarize

HEADER = [
    "Invoice", "StockCode", "Description", "Quantity",
    "InvoiceDate", "Price", "Customer ID", "Country",
]


def row(invoice, when, stock_code="85048", customer_id=13085):
    return [invoice, stock_code, "LIGHTS", 12, when, 6.95, customer_id, "France"]


def make_workbook(path, first, second, header=HEADER):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in (("Year 2009-2010", first), ("Year 2010-2011", second)):
        ws = wb.create_sheet(title)
        ws.append(header)
        for r in rows:
            ws.append(r)
    wb.save(path)


def load(tmp_path, first, second):
    xlsx, db = tmp_path / "in.xlsx", tmp_path / "retail.db"
    make_workbook(xlsx, first, second)
    build_database(xlsx, db)
    return db


def query(db, sql):
    with closing(sqlite3.connect(db)) as con:
        return con.execute(sql).fetchall()


def test_sales_table_has_requested_columns_and_flags(tmp_path):
    db = load(tmp_path, [row(489434, datetime(2009, 12, 1, 7, 45))], [])

    columns = [c[1] for c in query(db, "PRAGMA table_info(sales)")]

    assert columns == [
        "invoice", "stock_code", "description", "quantity", "invoice_date",
        "price", "customer_id", "country", "is_cancelled", "is_missing_customer",
    ]


def test_values_are_stored_with_stable_types(tmp_path):
    db = load(tmp_path, [row(489434, datetime(2009, 12, 1, 7, 45), stock_code=85048)], [])

    assert query(db, "SELECT * FROM sales") == [(
        "489434", "85048", "LIGHTS", 12, "2009-12-01 07:45:00",
        6.95, 13085, "France", 0, 0,
    )]


def test_overlap_period_is_taken_from_second_sheet_only(tmp_path):
    before = row(1, datetime(2010, 11, 30, 23, 59))
    start = row(2, datetime(2010, 12, 1, 0, 0))
    end = row(3, datetime(2010, 12, 9, 20, 1))
    later = row(4, datetime(2011, 1, 1, 9, 0))
    db = load(tmp_path, [before, start, end], [start, end, later])

    invoices = query(db, "SELECT invoice FROM sales ORDER BY invoice")

    assert invoices == [("1",), ("2",), ("3",), ("4",)]


def test_repeated_lines_within_one_sheet_are_kept(tmp_path):
    line = row(5, datetime(2011, 1, 1, 9, 0))
    db = load(tmp_path, [], [line, line])

    assert query(db, "SELECT COUNT(*) FROM sales") == [(2,)]


def test_cancelled_and_missing_customer_rows_are_kept_and_flagged(tmp_path):
    when = datetime(2011, 1, 1, 9, 0)
    db = load(tmp_path, [], [
        row("C489449", when),
        row(489450, when, customer_id=None),
        row("A506401", when),
    ])

    flags = query(db, "SELECT invoice, customer_id, is_cancelled, is_missing_customer "
                      "FROM sales ORDER BY invoice")

    assert flags == [
        ("489450", None, 0, 1),
        ("A506401", 13085, 0, 0),
        ("C489449", 13085, 1, 0),
    ]


def test_rebuilding_replaces_the_table(tmp_path):
    db = load(tmp_path, [], [row(1, datetime(2011, 1, 1))])
    build_database(tmp_path / "in.xlsx", db)

    assert query(db, "SELECT COUNT(*) FROM sales") == [(1,)]


def test_unexpected_header_fails_and_keeps_existing_database(tmp_path):
    db = load(tmp_path, [], [row(1, datetime(2011, 1, 1))])
    bad = tmp_path / "bad.xlsx"
    make_workbook(bad, [], [], header=list(reversed(HEADER)))

    with pytest.raises(ValueError, match="header"):
        build_database(bad, db)

    assert query(db, "SELECT COUNT(*) FROM sales") == [(1,)]


def test_summary_counts(tmp_path):
    db = load(
        tmp_path,
        [row(1, datetime(2009, 12, 1, 7, 45), stock_code="A1", customer_id=1)],
        [
            row("C2", datetime(2011, 1, 1), stock_code="A1", customer_id=None),
            row(3, datetime(2011, 12, 9, 12, 50), stock_code="B2", customer_id=2),
            row("C4", datetime(2011, 2, 1), stock_code="B2", customer_id=2),
        ],
    )

    assert summarize(db) == {
        "rows": 4,
        "first_date": "2009-12-01 07:45:00",
        "last_date": "2011-12-09 12:50:00",
        "products": 2,
        "customers": 2,
        "cancelled": 2,
        "missing_customer": 1,
        "both_flags": 1,
    }
