from __future__ import annotations

from pathlib import Path

import nbformat as nbf


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "01_data_exploration.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text)


def code(text: str):
    return nbf.v4.new_code_cell(text)


def build_notebook():
    nb = nbf.v4.new_notebook()
    nb.cells = [
        md("# SalesLens - Data Exploration"),
        md(
            "## 1. Project Objective\n"
            "We inspect the raw Olist CSV files before any cleaning so we can understand their structure, quality, keys, dates, and relationships."
        ),
        code(
            "from pathlib import Path\n"
            "import sys\n\n"
            "project_root = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\n"
            "if str(project_root) not in sys.path:\n"
            "    sys.path.insert(0, str(project_root))\n\n"
            "import pandas as pd\n"
            "from src.raw_loader import list_raw_csv_files, load_raw_csv\n\n"
            "pd.set_option('display.max_columns', None)\n"
            "pd.set_option('display.width', 120)\n"
        ),
        md("## 2. Load Raw Data"),
        code("files = list_raw_csv_files()\nfiles"),
        md("## 3. Dataset Overview"),
        code(
            "data = {p.name: load_raw_csv(p.name) for p in files}\n"
            "overview = pd.DataFrame([\n"
            "    {\n"
            "        'Dataset': name,\n"
            "        'Nombre de lignes': len(df),\n"
            "        'Nombre de colonnes': len(df.columns),\n"
            "        'Valeurs manquantes': int(df.isna().sum().sum()),\n"
            "        'Doublons': int(df.duplicated().sum()),\n"
            "    }\n"
            "    for name, df in data.items()\n"
            "]).sort_values('Dataset')\n"
            "overview"
        ),
        md("## 4. Missing Values"),
        code(
            "for name, df in data.items():\n"
            "    print(f'\\n### {name}')\n"
            "    print(df.isna().sum().sort_values(ascending=False))\n"
        ),
        md("## 5. Duplicate Records"),
        code(
            "for name, df in data.items():\n"
            "    print(f'{name}: {df.duplicated().sum()} duplicates')\n"
        ),
        md("## 6. Identifiers and Relationships"),
        code(
            "for name, df in data.items():\n"
            "    print(f'\\n### {name}')\n"
            "    id_cols = [c for c in df.columns if c.endswith('_id') or c.endswith('_code_prefix') or c in {'review_id', 'order_item_id', 'payment_sequential'}]\n"
            "    for c in id_cols:\n"
            "        print(f'{c}: unique={df[c].nunique(dropna=False)} / rows={len(df)}')\n"
        ),
        md("## 7. Date Columns"),
        code(
            "date_candidates = {\n"
            "    'olist_order_items_dataset.csv': ['shipping_limit_date'],\n"
            "    'olist_order_reviews_dataset.csv': ['review_creation_date', 'review_answer_timestamp'],\n"
            "    'olist_orders_dataset.csv': [\n"
            "        'order_purchase_timestamp', 'order_approved_at',\n"
            "        'order_delivered_carrier_date', 'order_delivered_customer_date',\n"
            "        'order_estimated_delivery_date']\n"
            "}\n"
            "for name, cols in date_candidates.items():\n"
            "    df = data[name]\n"
            "    print(f'\\n### {name}')\n"
            "    for c in cols:\n"
            "        parsed = pd.to_datetime(df[c], errors='coerce')\n"
            "        print(c, '| dtype=', df[c].dtype, '| parsed_dtype=', parsed.dtype, '| min=', parsed.min(), '| max=', parsed.max())\n"
        ),
        md("## 8. Numerical Variables"),
        code(
            "numeric_cols = {\n"
            "    'olist_order_items_dataset.csv': ['price', 'freight_value'],\n"
            "    'olist_order_payments_dataset.csv': ['payment_installments', 'payment_value'],\n"
            "    'olist_order_reviews_dataset.csv': ['review_score'],\n"
            "    'olist_products_dataset.csv': ['product_name_lenght', 'product_description_lenght', 'product_photos_qty', 'product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm'],\n"
            "}\n"
            "for name, cols in numeric_cols.items():\n"
            "    df = data[name]\n"
            "    print(f'\\n### {name}')\n"
            "    print(df[cols].describe().T[['count', 'mean', 'min', '50%', 'max']])\n"
        ),
        md("## 9. Categorical Variables"),
        code(
            "cat_cols = {\n"
            "    'olist_orders_dataset.csv': ['order_status'],\n"
            "    'olist_order_payments_dataset.csv': ['payment_type'],\n"
            "    'olist_customers_dataset.csv': ['customer_state'],\n"
            "    'olist_sellers_dataset.csv': ['seller_state'],\n"
            "    'olist_products_dataset.csv': ['product_category_name'],\n"
            "}\n"
            "for name, cols in cat_cols.items():\n"
            "    df = data[name]\n"
            "    print(f'\\n### {name}')\n"
            "    for c in cols:\n"
            "        print(f'\\n{c}')\n"
            "        print(df[c].value_counts(dropna=False).head(10))\n"
        ),
        md(
            "## 10. Initial Observations\n"
            "- The data covers the 2016-2018 Olist marketplace period.\n"
            "- Orders, customers, products, sellers, payments, reviews, and geolocation data are split across separate tables.\n"
            "- `order_items` is the most granular transactional table, so one order can appear multiple times there.\n"
            "- `geolocation` has many duplicate rows, which suggests repeated postal-code/location combinations rather than a clean unique list.\n"
            "- `order_reviews` contains a lot of missing comment fields, which is expected for optional text feedback.\n"
            "- Several date columns are stored as text and will need conversion later, but not yet in this step."
        ),
    ]
    return nb


def main() -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as f:
        nbf.write(build_notebook(), f)
    print(f"Wrote {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
