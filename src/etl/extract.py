"""Read the immutable processed SalesLens CSV layer."""

from collections.abc import Callable
from pathlib import Path

import pandas as pd


SOURCE_FILES = {
    "customers": "customers_clean.csv",
    "geolocation": "geolocation_clean.csv",
    "orders": "orders_clean.csv",
    "order_items": "order_items_clean.csv",
    "order_payments": "order_payments_clean.csv",
    "order_reviews": "order_reviews_clean.csv",
    "products": "products_clean.csv",
    "product_category_translation": "product_category_translation_clean.csv",
    "sellers": "sellers_clean.csv",
}

DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
}


def extract_processed_data(
    processed_dir: Path, log: Callable[[str], None] = print
) -> dict[str, pd.DataFrame]:
    """Read all processed source files and explicitly parse declared timestamps."""
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in SOURCE_FILES.items():
        path = processed_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Processed source file not found: {path}")
        frame = pd.read_csv(path, parse_dates=DATE_COLUMNS.get(name))
        frames[name] = frame
        log(f"Read {filename}: {len(frame):,} rows, {len(frame.columns)} columns")
    return frames
