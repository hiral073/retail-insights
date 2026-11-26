---
name: retail-data-rules
description: Use when writing SQL, Python or Excel logic for revenue, orders, customers or demand in this project.
---

# Retail data rules

Data lives in the SQLite database `retail.db`.

## Source

Always query the `clean_sales` view, never the raw `sales` table. This applies to
SQL, to Python, and to any data that feeds Excel.

`clean_sales` is defined in `sql/01_clean_sales.sql`. It excludes:

- cancelled invoices (`invoice` starts with `C`)
- rows with a quantity of zero or less
- rows with a price of zero or less
- non-product stock codes, matched regardless of letter case: `POST`, `DOT`, `M`,
  `D`, `S`, `B`, `BANK CHARGES`, `ADJUST`, `ADJUST2`, `AMAZONFEE`, `CRUK`,
  `PADS`, `TEST001`, `TEST002`

The view already applies these filters. Do not repeat them in queries.

## Revenue

Revenue is `quantity * price`, in pounds (GBP).

## Customers

Customer analysis also excludes rows with a missing customer ID:

```sql
SELECT customer_id, SUM(quantity * price) AS revenue
FROM clean_sales
WHERE customer_id IS NOT NULL
GROUP BY customer_id;
```

Revenue, order and demand totals keep those rows.

## Dates

The data ends on 9 Dec 2011, so December 2011 is a partial month. Do not compare
it with full months without saying so, or exclude it from the comparison.
