"""Read-only reconciliation of SalesLens metrics from processed Olist CSVs.

Run from any directory with the project environment:
    python scripts/audit_metrics.py

This script does not connect to PostgreSQL or inspect Power BI DAX. Delivery
calendar-day results reproduce the logic in sql/02_analytics.sql on the CSVs.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def read(name: str, **kwargs: object) -> pd.DataFrame:
    path = PROCESSED / f"{name}_clean.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing processed input: {path}")
    return pd.read_csv(path, **kwargs)


def decimal_sum(values: pd.Series) -> Decimal:
    return sum((Decimal(value) for value in values.dropna().astype(str)), Decimal("0"))


def main() -> None:
    orders = read("orders", parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"])
    items = read("order_items", dtype={"price": "string", "freight_value": "string"})
    payments = read("order_payments", dtype={"payment_value": "string"})
    reviews = read("order_reviews")
    customers = read("customers")
    products = read("products")
    sellers = read("sellers")

    item_price = pd.to_numeric(items["price"], errors="raise")
    item_freight = pd.to_numeric(items["freight_value"], errors="raise")
    payment_value = pd.to_numeric(payments["payment_value"], errors="raise")
    revenue = decimal_sum(items["price"])
    freight = decimal_sum(items["freight_value"])
    payment_total = decimal_sum(payments["payment_value"])

    itemized_order_ids = set(items["order_id"])
    source_order_ids = set(orders["order_id"])
    eligible = orders.dropna(
        subset=["order_purchase_timestamp", "order_delivered_customer_date"]
    ).copy()
    timestamp_days = (
        eligible["order_delivered_customer_date"] - eligible["order_purchase_timestamp"]
    ).dt.total_seconds() / 86_400
    calendar_days = (
        eligible["order_delivered_customer_date"].dt.normalize()
        - eligible["order_purchase_timestamp"].dt.normalize()
    ).dt.days

    category_cols = [
        column
        for column in ["product_category_name", "product_category_name_english"]
        if column in products.columns
    ]
    category_products = products[["product_id", *category_cols]].drop_duplicates("product_id")
    category_sales = items.assign(
        price_numeric=item_price.to_numpy()
    ).merge(category_products, on="product_id", how="left", validate="many_to_one")
    if "product_category_name_english" in category_sales:
        category_sales["category"] = category_sales["product_category_name_english"].fillna(
            category_sales.get("product_category_name")
        )
    else:
        category_sales["category"] = category_sales.get("product_category_name")
    category_sales["category"] = category_sales["category"].fillna("not_classified")
    top_revenue_category = category_sales.groupby("category")["price_numeric"].sum().idxmax()
    top_item_category = category_sales.groupby("category").size().idxmax()

    item_orders = items.merge(
        orders[["order_id", "customer_id", "order_purchase_timestamp"]],
        on="order_id",
        how="left",
        validate="many_to_one",
    )
    customer_states = customers[["customer_id", "customer_state"]]
    state_sales = item_orders.merge(
        customer_states, on="customer_id", how="left", validate="many_to_one"
    )
    sp_sales = state_sales[state_sales["customer_state"] == "SP"]
    monthly = item_orders.assign(
        month=item_orders["order_purchase_timestamp"].dt.strftime("%Y-%m"),
        price_numeric=pd.to_numeric(item_orders["price"], errors="raise"),
    ).groupby("month").agg(revenue=("price_numeric", "sum"), orders=("order_id", "nunique"))
    peak_month = monthly["revenue"].idxmax()
    payment_groups = payments.assign(
        payment_value_numeric=payment_value.to_numpy()
    ).groupby("payment_type").agg(
        amount=("payment_value_numeric", "sum"),
        orders=("order_id", "nunique"),
        allocations=("order_id", "size"),
    )
    credit_card = payment_groups.loc["credit_card"]

    review_by_order = reviews.groupby("order_id", as_index=False).agg(
        mean_review_score=("review_score", "mean")
    )
    satisfaction = eligible.assign(delivery_days=timestamp_days.to_numpy()).merge(
        review_by_order, on="order_id", how="inner", validate="one_to_one"
    )

    quality = {
        "order_id_duplicates": int(orders["order_id"].duplicated().sum()),
        "customer_id_duplicates": int(customers["customer_id"].duplicated().sum()),
        "product_id_duplicates": int(products["product_id"].duplicated().sum()),
        "seller_id_duplicates": int(sellers["seller_id"].duplicated().sum()),
        "duplicate_order_item_keys": int(items.duplicated(["order_id", "order_item_id"]).sum()),
        "duplicate_payment_keys": int(payments.duplicated(["order_id", "payment_sequential"]).sum()),
        "duplicate_order_review_keys": int(reviews.duplicated(["order_id", "review_id"]).sum()),
        "item_order_ids_missing_from_orders": len(set(items["order_id"]) - source_order_ids),
        "payment_order_ids_missing_from_orders": len(set(payments["order_id"]) - source_order_ids),
        "review_order_ids_missing_from_orders": len(set(reviews["order_id"]) - source_order_ids),
        "item_product_ids_missing_from_products": len(set(items["product_id"]) - set(products["product_id"])),
        "item_seller_ids_missing_from_sellers": len(set(items["seller_id"]) - set(sellers["seller_id"])),
        "negative_timestamp_delivery_durations": int((timestamp_days < 0).sum()),
        "negative_calendar_delivery_durations": int((calendar_days < 0).sum()),
        "null_item_prices": int(items["price"].isna().sum()),
        "null_item_freight": int(items["freight_value"].isna().sum()),
        "null_payment_values": int(payments["payment_value"].isna().sum()),
        "null_review_scores": int(reviews["review_score"].isna().sum()),
        "missing_required_order_fields": int(orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_estimated_delivery_date"]].isna().sum().sum()),
        "missing_required_item_fields": int(items[["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date"]].isna().sum().sum()),
        "missing_required_payment_fields": int(payments[["order_id", "payment_sequential", "payment_type", "payment_installments"]].isna().sum().sum()),
        "missing_required_review_fields": int(reviews[["order_id", "review_id", "review_creation_date"]].isna().sum().sum()),
    }

    result = {
        "source_scope": "data/processed/*_clean.csv; CSV calculations only",
        "counts": {
            "orders": int(orders["order_id"].nunique()),
            "orders_with_items": len(itemized_order_ids),
            "orders_without_items": len(source_order_ids - itemized_order_ids),
            "order_item_rows": len(items),
            "payment_allocation_rows": len(payments),
            "review_rows": len(reviews),
            "unique_customer_ids": int(customers["customer_id"].nunique()),
            "unique_customer_unique_ids": int(customers["customer_unique_id"].nunique()),
            "unique_products": int(products["product_id"].nunique()),
            "unique_sellers": int(sellers["seller_id"].nunique()),
        },
        "sales": {
            "product_revenue_brl": str(revenue.quantize(Decimal("0.01"))),
            "freight_brl": str(freight.quantize(Decimal("0.01"))),
            "aov_brl": str((revenue / Decimal(len(itemized_order_ids))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "freight_pct_of_product_revenue": str((freight / revenue * Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        },
        "payments": {
            "payment_value_brl": str(payment_total.quantize(Decimal("0.01"))),
            "credit_card_payment_value_brl": round(float(credit_card["amount"]), 2),
            "credit_card_distinct_orders": int(credit_card["orders"]),
            "credit_card_allocations": int(credit_card["allocations"]),
        },
        "reviews": {
            "rows": len(reviews),
            "mean_score": round(float(reviews["review_score"].mean()), 8),
            "orders_with_multiple_review_rows": int((reviews.groupby("order_id").size() > 1).sum()),
        },
        "delivery": {
            "same_eligible_orders_for_both_methods": len(eligible),
            "missing_delivery_timestamps": int(orders["order_delivered_customer_date"].isna().sum()),
            "timestamp_mean_days": round(float(timestamp_days.mean()), 8),
            "calendar_date_mean_days_csv_reproduction": round(float(calendar_days.mean()), 8),
            "timestamp_median_days": round(float(timestamp_days.median()), 8),
            "mean_delivery_days_review_score_per_order_correlation": round(
                float(satisfaction[["delivery_days", "mean_review_score"]].corr().iloc[0, 1]), 8
            ),
        },
        "insights": {
            "top_category_by_product_revenue": {
                "category": top_revenue_category,
                "revenue_brl": round(float(category_sales.loc[category_sales["category"] == top_revenue_category, "price_numeric"].sum()), 2),
            },
            "top_category_by_item_count": {
                "category": top_item_category,
                "items": int((category_sales["category"] == top_item_category).sum()),
            },
            "SP_customer_state": {
                "itemized_orders": int(sp_sales["order_id"].nunique()),
                "product_revenue_brl": round(float(sp_sales["price"].astype(float).sum()), 2),
            },
            "peak_product_revenue_month": {
                "month": peak_month,
                "revenue_brl": round(float(monthly.loc[peak_month, "revenue"]), 2),
                "itemized_orders": int(monthly.loc[peak_month, "orders"]),
            },
            "revenue_per_unique_customer_brl": round(float(revenue / Decimal(customers["customer_unique_id"].nunique())), 2),
            "all_source_orders_per_unique_customer": round(len(source_order_ids) / customers["customer_unique_id"].nunique(), 8),
            "itemized_orders_per_unique_customer": round(len(itemized_order_ids) / customers["customer_unique_id"].nunique(), 8),
        },
        "integrity_checks": quality,
        "integrity_passed": not any(quality.values()),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    if any(quality.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
