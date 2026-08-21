# SalesLens Data Cleaning Report

This report documents the first reproducible cleaning pass on the Olist raw CSV files.

## Main decisions
- Convert date columns to datetime during Python processing.
- When exported to CSV, dates are serialized as text because CSV does not preserve data types.
- When reloading processed CSVs, date columns must be parsed explicitly as dates.
- Remove exact duplicate rows from geolocation only.
- Keep missing review comment fields because they are optional feedback, not necessarily errors.
- Keep missing delivery timestamps because they may be meaningful for undelivered orders.
- Add the English product category translation while preserving the original Portuguese category.

## Product category translation
- Products with an English translation: 32328
- Products without an English translation: 623
- Original Portuguese category preserved: yes
- Original categories removed: no
- Categories without translation are kept as NULL/NaN and can be handled later depending on analysis needs.
- Portuguese categories without translation:
  - portateis_cozinha_e_preparadores_de_alimentos: 10 products
  - pc_gamer: 3 products

## Reproducibility
- Run the cleaning from the terminal with `.\.venv\Scripts\python.exe -m src.clean_data`.
- `data/raw/` is the immutable source layer.
- `data/processed/` is generated output and can be rebuilt at any time by rerunning the script.

## Dataset summary
### olist_customers_dataset.csv
- Rows before: 99441
- Rows after: 99441
- Columns: 5
- Missing values before: 0
- Missing values after: 0
- Duplicates before: 0
- Duplicates after: 0

### olist_geolocation_dataset.csv
- Rows before: 1000163
- Rows after: 738332
- Columns: 5
- Missing values before: 0
- Missing values after: 0
- Duplicates before: 261831
- Duplicates after: 0

### olist_order_items_dataset.csv
- Rows before: 112650
- Rows after: 112650
- Columns: 7
- Missing values before: 0
- Missing values after: 0
- Duplicates before: 0
- Duplicates after: 0

### olist_order_payments_dataset.csv
- Rows before: 103886
- Rows after: 103886
- Columns: 5
- Missing values before: 0
- Missing values after: 0
- Duplicates before: 0
- Duplicates after: 0

### olist_order_reviews_dataset.csv
- Rows before: 99224
- Rows after: 99224
- Columns: 7
- Missing values before: 145903
- Missing values after: 145903
- Duplicates before: 0
- Duplicates after: 0

### olist_orders_dataset.csv
- Rows before: 99441
- Rows after: 99441
- Columns: 8
- Missing values before: 4908
- Missing values after: 4908
- Duplicates before: 0
- Duplicates after: 0

### olist_products_dataset.csv
- Rows before: 32951
- Rows after: 32951
- Columns: 10
- Missing values before: 2448
- Missing values after: 3071
- Duplicates before: 0
- Duplicates after: 0

### olist_sellers_dataset.csv
- Rows before: 3095
- Rows after: 3095
- Columns: 4
- Missing values before: 0
- Missing values after: 0
- Duplicates before: 0
- Duplicates after: 0

### product_category_name_translation.csv
- Rows before: 71
- Rows after: 71
- Columns: 2
- Missing values before: 0
- Missing values after: 0
- Duplicates before: 0
- Duplicates after: 0
