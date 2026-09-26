"""Build target-shaped DataFrames while preserving the validated source grain."""

from collections.abc import Mapping

import pandas as pd


DIMENSION_COLUMNS = {
    "dim_date": [
        "date_key", "calendar_date", "year", "quarter", "month_number", "month_name",
        "year_month", "day_of_month", "day_of_week", "day_name", "is_weekend",
    ],
    "dim_customer": [
        "customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city",
        "customer_state",
    ],
    "dim_product": [
        "product_id", "product_category_name", "product_category_name_english",
        "product_name_length", "product_description_length", "product_photos_qty",
        "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
    ],
    "dim_seller": [
        "seller_id", "seller_zip_code_prefix", "seller_city", "seller_state",
    ],
}

FACT_COLUMNS = {
    "fact_sales": [
        "order_id", "order_item_id", "customer_key", "product_key", "seller_key",
        "purchase_date_key", "approval_date_key", "shipping_limit_date_key",
        "carrier_date_key", "delivery_date_key", "estimated_delivery_date_key",
        "order_status", "price", "freight_value",
    ],
    "fact_payments": [
        "order_id", "customer_key", "purchase_date_key", "payment_sequential",
        "payment_type", "payment_installments", "payment_value",
    ],
    "fact_reviews": [
        "order_id", "review_id", "customer_key", "purchase_date_key",
        "review_creation_date_key", "review_answer_date_key", "review_score",
        "review_comment_title", "review_comment_message",
    ],
}

PRODUCT_INTEGER_COLUMNS = [
    "product_name_length",
    "product_description_length",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]


def _require_unique(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    duplicate_count = int(frame.duplicated(columns).sum())
    if duplicate_count:
        raise ValueError(f"{label} has {duplicate_count:,} duplicate natural keys: {columns}")


def _require_values(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = frame[columns].isna().sum()
    invalid = missing[missing > 0]
    if not invalid.empty:
        details = ", ".join(f"{column}={count:,}" for column, count in invalid.items())
        raise ValueError(f"{label} has missing required values: {details}")


def date_keys(values: pd.Series, required: bool = False) -> pd.Series:
    """Convert timestamps to nullable YYYYMMDD integer date keys."""
    timestamps = pd.to_datetime(values, errors="coerce")
    if required and timestamps.isna().any():
        raise ValueError(f"Required date column has {int(timestamps.isna().sum()):,} missing values")
    return pd.Series(
        pd.array(timestamps.dt.strftime("%Y%m%d"), dtype="Int64"), index=values.index
    )


def coerce_product_integer_columns(products: pd.DataFrame) -> pd.DataFrame:
    """Convert nullable product measurements to integers without replacing missing values."""
    converted = products.copy()
    for column in PRODUCT_INTEGER_COLUMNS:
        numeric_values = pd.to_numeric(converted[column], errors="raise")
        non_null_values = numeric_values.dropna()
        if not non_null_values.empty and (non_null_values % 1 != 0).any():
            raise ValueError(f"{column} contains non-integer values")
        converted[column] = numeric_values.astype("Int64")
    return converted


def build_dim_date(sources: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Generate all calendar days needed by the date roles in the physical schema."""
    date_sources = [
        sources["orders"][
            [
                "order_purchase_timestamp", "order_approved_at",
                "order_delivered_carrier_date", "order_delivered_customer_date",
                "order_estimated_delivery_date",
            ]
        ],
        sources["order_items"][["shipping_limit_date"]],
        sources["order_reviews"][["review_creation_date", "review_answer_timestamp"]],
    ]
    all_dates = pd.concat([frame.stack() for frame in date_sources], ignore_index=True)
    all_dates = pd.to_datetime(all_dates, errors="coerce").dropna().dt.normalize()
    if all_dates.empty:
        raise ValueError("No valid dates are available to build dim_date")

    calendar = pd.DataFrame({"calendar_date": pd.date_range(all_dates.min(), all_dates.max(), freq="D")})
    calendar["date_key"] = calendar["calendar_date"].dt.strftime("%Y%m%d").astype("int64")
    calendar["year"] = calendar["calendar_date"].dt.year.astype("int16")
    calendar["quarter"] = calendar["calendar_date"].dt.quarter.astype("int8")
    calendar["month_number"] = calendar["calendar_date"].dt.month.astype("int8")
    calendar["month_name"] = calendar["calendar_date"].dt.month_name()
    calendar["year_month"] = calendar["calendar_date"].dt.strftime("%Y-%m")
    calendar["day_of_month"] = calendar["calendar_date"].dt.day.astype("int8")
    calendar["day_of_week"] = calendar["calendar_date"].dt.isocalendar().day.astype("int8")
    calendar["day_name"] = calendar["calendar_date"].dt.day_name()
    calendar["is_weekend"] = calendar["day_of_week"].isin([6, 7])
    return calendar[DIMENSION_COLUMNS["dim_date"]]


def build_dimensions(sources: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Project processed dimension sources into the exact database column names."""
    customers = sources["customers"].copy()[DIMENSION_COLUMNS["dim_customer"]]
    products = sources["products"].rename(
        columns={
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        }
    )[DIMENSION_COLUMNS["dim_product"]]
    products = coerce_product_integer_columns(products)
    sellers = sources["sellers"].copy()[DIMENSION_COLUMNS["dim_seller"]]

    for label, frame, key, required in [
        ("dim_customer", customers, ["customer_id"], DIMENSION_COLUMNS["dim_customer"]),
        ("dim_product", products, ["product_id"], ["product_id"]),
        ("dim_seller", sellers, ["seller_id"], DIMENSION_COLUMNS["dim_seller"]),
    ]:
        _require_unique(frame, key, label)
        _require_values(frame, required, label)

    return {
        "dim_date": build_dim_date(sources),
        "dim_customer": customers,
        "dim_product": products,
        "dim_seller": sellers,
    }


def _map_key(
    frame: pd.DataFrame, source_column: str, target_column: str, lookup: Mapping[object, int]
) -> None:
    frame[target_column] = frame[source_column].map(lookup).astype("Int64")
    unresolved = int(frame[target_column].isna().sum())
    if unresolved:
        raise ValueError(
            f"Could not resolve {unresolved:,} {source_column} values to {target_column}"
        )


def _orders_for_facts(sources: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    orders = sources["orders"].copy()
    _require_unique(orders, ["order_id"], "orders")
    _require_values(orders, ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_estimated_delivery_date"], "orders")
    return orders


def build_facts(
    sources: Mapping[str, pd.DataFrame], lookups: Mapping[str, Mapping[object, int]]
) -> dict[str, pd.DataFrame]:
    """Build facts after PostgreSQL has assigned dimension surrogate keys."""
    orders = _orders_for_facts(sources)
    customer_lookup = lookups["customer"]
    product_lookup = lookups["product"]
    seller_lookup = lookups["seller"]

    sales = sources["order_items"].merge(
        orders, on="order_id", how="left", validate="many_to_one"
    )
    _require_unique(sales, ["order_id", "order_item_id"], "fact_sales source")
    _require_values(
        sales,
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value", "customer_id"],
        "fact_sales source",
    )
    _map_key(sales, "customer_id", "customer_key", customer_lookup)
    _map_key(sales, "product_id", "product_key", product_lookup)
    _map_key(sales, "seller_id", "seller_key", seller_lookup)
    sales["purchase_date_key"] = date_keys(sales["order_purchase_timestamp"], required=True)
    sales["approval_date_key"] = date_keys(sales["order_approved_at"])
    sales["shipping_limit_date_key"] = date_keys(sales["shipping_limit_date"], required=True)
    sales["carrier_date_key"] = date_keys(sales["order_delivered_carrier_date"])
    sales["delivery_date_key"] = date_keys(sales["order_delivered_customer_date"])
    sales["estimated_delivery_date_key"] = date_keys(sales["order_estimated_delivery_date"], required=True)
    sales = sales[FACT_COLUMNS["fact_sales"]]

    payments = sources["order_payments"].merge(
        orders[["order_id", "customer_id", "order_purchase_timestamp"]],
        on="order_id", how="left", validate="many_to_one"
    )
    _require_unique(payments, ["order_id", "payment_sequential"], "fact_payments source")
    _require_values(
        payments,
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value", "customer_id"],
        "fact_payments source",
    )
    _map_key(payments, "customer_id", "customer_key", customer_lookup)
    payments["purchase_date_key"] = date_keys(payments["order_purchase_timestamp"], required=True)
    payments = payments[FACT_COLUMNS["fact_payments"]]

    reviews = sources["order_reviews"].merge(
        orders[["order_id", "customer_id", "order_purchase_timestamp"]],
        on="order_id", how="left", validate="many_to_one"
    )
    _require_unique(reviews, ["order_id", "review_id"], "fact_reviews source")
    _require_values(
        reviews,
        ["order_id", "review_id", "review_score", "review_creation_date", "customer_id"],
        "fact_reviews source",
    )
    _map_key(reviews, "customer_id", "customer_key", customer_lookup)
    reviews["purchase_date_key"] = date_keys(reviews["order_purchase_timestamp"], required=True)
    reviews["review_creation_date_key"] = date_keys(reviews["review_creation_date"], required=True)
    reviews["review_answer_date_key"] = date_keys(reviews["review_answer_timestamp"])
    reviews = reviews[FACT_COLUMNS["fact_reviews"]]

    return {"fact_sales": sales, "fact_payments": payments, "fact_reviews": reviews}
