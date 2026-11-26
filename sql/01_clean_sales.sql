-- Product sales used for revenue, order, customer and demand analysis.
-- Customer analysis must additionally filter `customer_id IS NOT NULL`.
DROP VIEW IF EXISTS clean_sales;

CREATE VIEW clean_sales AS
SELECT *
FROM sales
WHERE invoice NOT LIKE 'C%'                      -- cancelled invoices
  AND quantity > 0
  AND price > 0
  AND UPPER(TRIM(stock_code)) NOT IN (           -- non-product codes, any case
      'POST', 'DOT', 'M', 'D', 'S', 'B', 'BANK CHARGES', 'ADJUST', 'ADJUST2',
      'AMAZONFEE', 'CRUK', 'PADS', 'TEST001', 'TEST002'
  );
