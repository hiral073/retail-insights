# retail-insights

Loads the Online Retail II dataset (`online_retail_II.xlsx`) into a SQLite
database, `retail.db`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install "openpyxl>=3.1" "pytest>=8"
```

## Get the data and build the database

The dataset is not stored in this repository. Do the setup above first, then:

1. Open the UCI Machine Learning Repository page for
   [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii).
2. Click **Download** to get the zip file (about 43.5 MB).
3. Extract `online_retail_II.xlsx` into the project root, next to `load_data.py`.
   Keep the file name, and do not edit or re-save the workbook.
4. From the project root, run `.venv\Scripts\python load_data.py`.

This creates `retail.db` with the `sales` table (1,044,848 rows) and the
`clean_sales` view.

Dataset licence: CC BY 4.0. Citation: Chen, D. (2012). Online Retail II. UCI
Machine Learning Repository. <https://doi.org/10.24432/C5CG6D>

## Run

```powershell
.venv\Scripts\python load_data.py   # rebuilds retail.db and prints a summary
.venv\Scripts\python -m pytest      # runs the tests
```

The workbook is only read, never modified.

## Clean data and checks

Analysis uses the `clean_sales` view (`sql/01_clean_sales.sql`), not `sales`.
`load_data.py` creates the views after loading. The rules are in
`.claude/skills/retail-data-rules/SKILL.md`.

```powershell
.venv\Scripts\python checks\run_checks.py
```

The checks rebuild the views on a temporary copy of `retail.db`, so `retail.db`
is not changed. Exit code 2 means a check failed. A Claude Code hook in
`.claude/settings.json` runs them after any edit to a `.sql` file in `sql/`.

After changing a view, apply it to `retail.db`:

```powershell
.venv\Scripts\python -c "from views import apply_views; apply_views('retail.db')"
```

## Table `sales`

| Column | Type | Notes |
|---|---|---|
| `invoice` | TEXT | Starts with `C` for cancellations |
| `stock_code` | TEXT | Stored as in the source, case included |
| `description` | TEXT | May be NULL |
| `quantity` | INTEGER | May be negative |
| `invoice_date` | TEXT | `YYYY-MM-DD HH:MM:SS` |
| `price` | REAL | Unit price; may be negative |
| `customer_id` | INTEGER | NULL when missing |
| `country` | TEXT | |
| `is_cancelled` | INTEGER | 1 if `invoice` starts with `C` |
| `is_missing_customer` | INTEGER | 1 if `customer_id` is NULL |

## Data handling

- Both sheets contain 1 Dec 2010 to 9 Dec 2010. That period is taken from the
  `Year 2010-2011` sheet only.
- No other rows are removed or altered. Repeated lines within a sheet, invoices
  starting with `A`, and non-product stock codes remain in the table.
