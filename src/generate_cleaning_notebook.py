from __future__ import annotations

from pathlib import Path

import nbformat as nbf


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "02_data_cleaning.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text)


def code(text: str):
    return nbf.v4.new_code_cell(text)


def build_notebook():
    return nbf.v4.new_notebook(
        cells=[
            md("# SalesLens - Data Cleaning"),
            md("## 1. Cleaning Objectives\nWe create a reproducible first cleaning pass from the raw Olist files into processed CSVs without touching the originals."),
            code(
                "from pathlib import Path\n"
                "import sys\n"
                "project_root = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\n"
                "if str(project_root) not in sys.path:\n"
                "    sys.path.insert(0, str(project_root))\n"
                "from src.clean_data import clean_datasets, export_cleaned, validate_cleaned_datasets, count_orphan_rows, DOCS_REPORT\n"
                "import pandas as pd\n"
            ),
            md("## 2. Load Raw Data"),
            code("cleaned, stats = clean_datasets()\nstats"),
            md("## 3. Data Type Corrections"),
            code(
                "for name in ['olist_orders_dataset.csv','olist_order_items_dataset.csv','olist_order_reviews_dataset.csv']:\n"
                "    print(f'\\n{name}')\n"
                "    print(cleaned[name].dtypes)\n"
            ),
            md("## 4. Missing Values"),
            code(
                "for name, df in cleaned.items():\n"
                "    print(f'\\n### {name}')\n"
                "    print(df.isna().sum().sort_values(ascending=False).head(10))\n"
            ),
            md("## 5. Duplicate Records"),
            code(
                "for name, df in cleaned.items():\n"
                "    print(f'{name}: {df.duplicated().sum()} duplicates')\n"
            ),
            md("## 6. Invalid / Inconsistent Values"),
            code(
                "checks = {\n"
                "    'olist_order_items_dataset.csv': ['price', 'freight_value'],\n"
                "    'olist_order_payments_dataset.csv': ['payment_installments', 'payment_value'],\n"
                "    'olist_order_reviews_dataset.csv': ['review_score'],\n"
                "    'olist_products_dataset.csv': ['product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm']\n"
                "}\n"
                "for name, cols in checks.items():\n"
                "    df = cleaned[name]\n"
                "    print(f'\\n### {name}')\n"
                "    for c in cols:\n"
                "        print(c, 'min=', df[c].min(), 'max=', df[c].max())\n"
            ),
            md("## 7. Referential Integrity"),
            code(
                "orders = cleaned['olist_orders_dataset.csv']\n"
                "customers = cleaned['olist_customers_dataset.csv']\n"
                "items = cleaned['olist_order_items_dataset.csv']\n"
                "products = cleaned['olist_products_dataset.csv']\n"
                "sellers = cleaned['olist_sellers_dataset.csv']\n"
                "print('orders without customer:', count_orphan_rows(orders, customers[['customer_id']], 'customer_id'))\n"
                "print('items without order:', count_orphan_rows(items, orders[['order_id']], 'order_id'))\n"
                "print('items without product:', count_orphan_rows(items, products[['product_id']], 'product_id'))\n"
                "print('items without seller:', count_orphan_rows(items, sellers[['seller_id']], 'seller_id'))\n"
            ),
            md("## 8. Cleaning Decisions"),
            md(
                "- Convert date columns to datetime.\n"
                "- Remove exact geolocation duplicates.\n"
                "- Keep missing review text fields and missing delivery timestamps.\n"
                "- Preserve original product category and add English translation."
            ),
            md("## 9. Export Processed Data"),
            code("export_cleaned(cleaned)\nprint('processed exported')"),
            md("## 10. Validation"),
            code(
                "validate_cleaned_datasets(cleaned)\n"
                "print('validation passed')\n"
                "print(DOCS_REPORT.read_text(encoding='utf-8').splitlines()[:10])\n"
            ),
        ]
    )


def main() -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as f:
        nbf.write(build_notebook(), f)
    print(f"Wrote {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
