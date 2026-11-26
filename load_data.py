"""Load the Online Retail II workbook into the `sales` table of retail.db."""

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import openpyxl

from views import apply_views

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "online_retail_II.xlsx"
DATABASE = ROOT / "retail.db"

FIRST_SHEET = "Year 2009-2010"
SECOND_SHEET = "Year 2010-2011"
# Both sheets hold 1-9 Dec 2010. The first sheet's rows from this moment on are
# skipped, so that period comes from the second sheet only.
OVERLAP_START = datetime(2010, 12, 1)

HEADER = (
    "Invoice", "StockCode", "Description", "Quantity",
    "InvoiceDate", "Price", "Customer ID", "Country",
)

SCHEMA = """
CREATE TABLE sales (
    invoice             TEXT    NOT NULL,
    stock_code          TEXT    NOT NULL,
    description         TEXT,
    quantity            INTEGER NOT NULL,
    invoice_date        TEXT    NOT NULL,
    price               REAL    NOT NULL,
    customer_id         INTEGER,
    country             TEXT    NOT NULL,
    is_cancelled        INTEGER NOT NULL CHECK (is_cancelled IN (0, 1)),
    is_missing_customer INTEGER NOT NULL CHECK (is_missing_customer IN (0, 1))
)
"""


def _text(value):
    return None if value is None else str(value)


def _sheet_rows(workbook, name):
    rows = workbook[name].iter_rows(values_only=True)
    header = next(rows, None)
    if header != HEADER:
        raise ValueError(f"Unexpected header in sheet {name!r}: {header}")
    return rows


def _record(row):
    invoice, stock_code, description, quantity, date, price, customer_id, country = row
    invoice = _text(invoice)
    return (
        invoice,
        _text(stock_code),
        _text(description),
        quantity,
        date.isoformat(sep=" ", timespec="seconds"),
        price,
        None if customer_id is None else int(customer_id),
        country,
        int(invoice.startswith("C")),
        int(customer_id is None),
    )


def _records(workbook):
    for row in _sheet_rows(workbook, FIRST_SHEET):
        if row[4] < OVERLAP_START:
            yield _record(row)
    for row in _sheet_rows(workbook, SECOND_SHEET):
        yield _record(row)


def build_database(source=SOURCE, database=DATABASE):
    """Rebuild `database` from `source`. The source is opened read-only.

    The database is written to a temporary file first, so a failed run leaves
    any existing database untouched.
    """
    database = Path(database)
    partial = database.with_name(database.name + ".partial")
    partial.unlink(missing_ok=True)
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        with closing(sqlite3.connect(partial)) as con:
            with con:
                con.execute(SCHEMA)
                con.executemany(
                    "INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _records(workbook),
                )
        apply_views(partial)
        os.replace(partial, database)
    finally:
        workbook.close()
        partial.unlink(missing_ok=True)


def summarize(database=DATABASE):
    """Return headline counts for the `sales` table."""
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        con.row_factory = sqlite3.Row
        return dict(con.execute("""
            SELECT COUNT(*)                                   AS rows,
                   MIN(invoice_date)                          AS first_date,
                   MAX(invoice_date)                          AS last_date,
                   COUNT(DISTINCT stock_code)                 AS products,
                   COUNT(DISTINCT customer_id)                AS customers,
                   SUM(is_cancelled)                          AS cancelled,
                   SUM(is_missing_customer)                   AS missing_customer,
                   SUM(is_cancelled AND is_missing_customer)  AS both_flags
            FROM sales
        """).fetchone())


def main():
    print(f"Loading {SOURCE.name} into {DATABASE.name} ...")
    build_database()
    s = summarize()
    flagged_either = s["cancelled"] + s["missing_customer"] - s["both_flags"]
    print(f"Rows:                  {s['rows']:,}")
    print(f"Date range:            {s['first_date']} to {s['last_date']}")
    print(f"Unique products:       {s['products']:,}")
    print(f"Unique customers:      {s['customers']:,}")
    print(f"Flagged cancelled:     {s['cancelled']:,}")
    print(f"Flagged no customer:   {s['missing_customer']:,}")
    print(f"Flagged both:          {s['both_flags']:,}")
    print(f"Flagged at least once: {flagged_either:,}")


if __name__ == "__main__":
    main()
