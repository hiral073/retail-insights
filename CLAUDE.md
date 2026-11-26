# retail-insights

A sales health check plus a stock decision simulator, built on the Online Retail II dataset.

## Folder layout
- `online_retail_II.xlsx`: original data, two sheets
- `retail.db`: SQLite database built from the workbook
- `load_data.py`: builds `retail.db` (table `sales`) and its views
- `views.py`: applies the scripts in `sql/`
- `sql/`: view definitions (`01_clean_sales.sql`)
- `checks/run_checks.py`: data checks, also run by a hook after Claude edits `sql/*.sql`
- `tests/`: pytest tests
- `.claude/`: hook settings and the `retail-data-rules` skill

## Rules
- Never modify `online_retail_II.xlsx`. `retail.db` is built from it and can be rebuilt.
- All analysis queries use the `clean_sales` view, never the raw `sales` table.
  Follow the `retail-data-rules` skill.
- Put business assumptions, such as lost-sale cost, in `config.yaml`. Do not hard-code
  them. `config.yaml` does not exist yet: create it with the first assumption.

## Commands
- Rebuild database: `.venv\Scripts\python load_data.py`
- Test: `.venv\Scripts\python -m pytest`
- Check data: `.venv\Scripts\python checks\run_checks.py`
