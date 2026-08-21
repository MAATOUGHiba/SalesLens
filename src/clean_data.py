from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.raw_loader import load_raw_csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DOCS_REPORT = PROJECT_ROOT / "docs" / "data_cleaning_report.md"


DATE_COLUMNS = {
    "olist_order_items_dataset.csv": ["shipping_limit_date"],
    "olist_order_reviews_dataset.csv": ["review_creation_date", "review_answer_timestamp"],
    "olist_orders_dataset.csv": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
}


def load_all_raw() -> dict[str, pd.DataFrame]:
    return {
        "olist_customers_dataset.csv": load_raw_csv("olist_customers_dataset.csv"),
        "olist_geolocation_dataset.csv": load_raw_csv("olist_geolocation_dataset.csv"),
        "olist_order_items_dataset.csv": load_raw_csv("olist_order_items_dataset.csv"),
        "olist_order_payments_dataset.csv": load_raw_csv("olist_order_payments_dataset.csv"),
        "olist_order_reviews_dataset.csv": load_raw_csv("olist_order_reviews_dataset.csv"),
        "olist_orders_dataset.csv": load_raw_csv("olist_orders_dataset.csv"),
        "olist_products_dataset.csv": load_raw_csv("olist_products_dataset.csv"),
        "olist_sellers_dataset.csv": load_raw_csv("olist_sellers_dataset.csv"),
        "product_category_name_translation.csv": load_raw_csv("product_category_name_translation.csv"),
    }


def parse_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    cleaned = df.copy()
    for col in columns:
        cleaned[col] = pd.to_datetime(cleaned[col], errors="coerce")
    return cleaned


def clean_products(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    cleaned = products.merge(translation, on="product_category_name", how="left")
    return cleaned


def clean_geolocation(geolocation: pd.DataFrame) -> pd.DataFrame:
    return geolocation.drop_duplicates().copy()


def clean_datasets() -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]:
    raw = load_all_raw()
    stats: dict[str, dict[str, int]] = {}

    cleaned: dict[str, pd.DataFrame] = {}
    for name, df in raw.items():
        cleaned[name] = df.copy()

    cleaned["olist_geolocation_dataset.csv"] = clean_geolocation(cleaned["olist_geolocation_dataset.csv"])
    cleaned["olist_products_dataset.csv"] = clean_products(
        cleaned["olist_products_dataset.csv"],
        cleaned["product_category_name_translation.csv"],
    )

    for name, cols in DATE_COLUMNS.items():
        cleaned[name] = parse_dates(cleaned[name], cols)

    for name, df in raw.items():
        before = len(df)
        after = len(cleaned[name])
        stats[name] = {
            "before_rows": before,
            "after_rows": after,
            "before_missing": int(df.isna().sum().sum()),
            "after_missing": int(cleaned[name].isna().sum().sum()),
            "before_duplicates": int(df.duplicated().sum()),
            "after_duplicates": int(cleaned[name].duplicated().sum()),
            "columns": len(cleaned[name].columns),
        }

    return cleaned, stats


def validate_cleaned_datasets(cleaned: dict[str, pd.DataFrame]) -> None:
    if cleaned["olist_orders_dataset.csv"]["order_id"].duplicated().any():
        raise ValueError("order_id must remain unique in orders")
    if cleaned["olist_customers_dataset.csv"]["customer_id"].duplicated().any():
        raise ValueError("customer_id must remain unique in customers")
    if cleaned["olist_products_dataset.csv"]["product_id"].duplicated().any():
        raise ValueError("product_id must remain unique in products")
    if cleaned["olist_sellers_dataset.csv"]["seller_id"].duplicated().any():
        raise ValueError("seller_id must remain unique in sellers")

    if cleaned["olist_order_items_dataset.csv"]["order_id"].isna().any():
        raise ValueError("order_items cannot contain missing order_id")

    if cleaned["olist_geolocation_dataset.csv"].duplicated().any():
        raise ValueError("geolocation duplicates should have been removed")


def export_cleaned(cleaned: dict[str, pd.DataFrame]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    mapping = {
        "olist_customers_dataset.csv": "customers_clean.csv",
        "olist_geolocation_dataset.csv": "geolocation_clean.csv",
        "olist_order_items_dataset.csv": "order_items_clean.csv",
        "olist_order_payments_dataset.csv": "order_payments_clean.csv",
        "olist_order_reviews_dataset.csv": "order_reviews_clean.csv",
        "olist_orders_dataset.csv": "orders_clean.csv",
        "olist_products_dataset.csv": "products_clean.csv",
        "olist_sellers_dataset.csv": "sellers_clean.csv",
        "product_category_name_translation.csv": "product_category_translation_clean.csv",
    }
    for raw_name, output_name in mapping.items():
        cleaned[raw_name].to_csv(PROCESSED_DIR / output_name, index=False)


def build_report(stats: dict[str, dict[str, int]], cleaned: dict[str, pd.DataFrame]) -> str:
    products = cleaned["olist_products_dataset.csv"]
    untranslated = products[products["product_category_name_english"].isna()]
    untranslated_summary = untranslated["product_category_name"].value_counts()
    lines = [
        "# SalesLens Data Cleaning Report",
        "",
        "This report documents the first reproducible cleaning pass on the Olist raw CSV files.",
        "",
        "## Main decisions",
        "- Convert date columns to datetime during Python processing.",
        "- When exported to CSV, dates are serialized as text because CSV does not preserve data types.",
        "- When reloading processed CSVs, date columns must be parsed explicitly as dates.",
        "- Remove exact duplicate rows from geolocation only.",
        "- Keep missing review comment fields because they are optional feedback, not necessarily errors.",
        "- Keep missing delivery timestamps because they may be meaningful for undelivered orders.",
        "- Add the English product category translation while preserving the original Portuguese category.",
        "",
        "## Product category translation",
        f"- Products with an English translation: {int(products['product_category_name_english'].notna().sum())}",
        f"- Products without an English translation: {int(untranslated.shape[0])}",
        f"- Original Portuguese category preserved: yes",
        f"- Original categories removed: no",
        "- Categories without translation are kept as NULL/NaN and can be handled later depending on analysis needs.",
        "- Portuguese categories without translation:",
    ]
    for category, count in untranslated_summary.items():
        lines.append(f"  - {category}: {int(count)} products")
    lines.extend(
        [
            "",
            "## Reproducibility",
            r"- Run the cleaning from the terminal with `.\.venv\Scripts\python.exe -m src.clean_data`.",
            "- `data/raw/` is the immutable source layer.",
            "- `data/processed/` is generated output and can be rebuilt at any time by rerunning the script.",
            "",
            "## Dataset summary",
        ]
    )
    for name, stat in stats.items():
        lines.extend(
            [
                f"### {name}",
                f"- Rows before: {stat['before_rows']}",
                f"- Rows after: {stat['after_rows']}",
                f"- Columns: {stat['columns']}",
                f"- Missing values before: {stat['before_missing']}",
                f"- Missing values after: {stat['after_missing']}",
                f"- Duplicates before: {stat['before_duplicates']}",
                f"- Duplicates after: {stat['after_duplicates']}",
                "",
            ]
        )
    DOCS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    return "\n".join(lines)


def count_orphan_rows(left: pd.DataFrame, right_keys: pd.DataFrame, key: str) -> int:
    merged = left[[key]].merge(right_keys[[key]].drop_duplicates(), on=key, how="left", indicator=True)
    return int((merged["_merge"] == "left_only").sum())


def run_cleaning() -> dict[str, pd.DataFrame]:
    cleaned, stats = clean_datasets()
    validate_cleaned_datasets(cleaned)
    export_cleaned(cleaned)
    DOCS_REPORT.write_text(build_report(stats, cleaned), encoding="utf-8")
    return cleaned


if __name__ == "__main__":
    run_cleaning()
