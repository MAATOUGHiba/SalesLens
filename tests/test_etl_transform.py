"""Focused unit tests for SalesLens ETL transformation rules."""

import re

import pandas as pd
import pytest

from src.etl.transform import coerce_product_integer_columns, build_facts, date_keys


def test_date_keys_use_yyyymmdd_and_keep_missing_values() -> None:
    values = pd.Series(["2017-11-24 10:00:00", None])
    result = date_keys(values)
    assert result.iloc[0] == 20171124
    assert pd.isna(result.iloc[1])


def test_product_integer_columns_drop_float_suffix_and_preserve_nulls() -> None:
    products = pd.DataFrame({
        "product_name_length": [40.0, None],
        "product_description_length": [500.0, None],
        "product_photos_qty": [2.0, None],
        "product_weight_g": [1000.0, None],
        "product_length_cm": [20.0, None],
        "product_height_cm": [10.0, None],
        "product_width_cm": [15.0, None],
    })

    result = coerce_product_integer_columns(products)

    assert str(result["product_name_length"].dtype) == "Int64"
    assert result.loc[0, "product_name_length"] == 40
    assert pd.isna(result.loc[1, "product_name_length"])
    assert all(str(result[column].dtype) == "Int64" for column in result.columns)


def test_fact_key_mapping_uses_technical_keys() -> None:
    sources = _minimal_sources()
    facts = build_facts(
        sources,
        {"customer": {"customer-business-id": 101}, "product": {"product-id": 202}, "seller": {"seller-id": 303}},
    )
    assert facts["fact_sales"].loc[0, "customer_key"] == 101
    assert facts["fact_sales"].loc[0, "product_key"] == 202
    assert facts["fact_sales"].loc[0, "seller_key"] == 303


def test_fact_grains_reject_duplicate_natural_keys() -> None:
    sources = _minimal_sources()
    sources["order_items"] = pd.concat([sources["order_items"], sources["order_items"]], ignore_index=True)
    with pytest.raises(ValueError, match="fact_sales source has 1 duplicate"):
        build_facts(sources, _lookups())


def test_fact_payments_and_reviews_keep_their_own_grains() -> None:
    facts = build_facts(_minimal_sources(), _lookups())
    assert len(facts["fact_payments"]) == 1
    assert len(facts["fact_reviews"]) == 1
    assert not facts["fact_payments"].duplicated(["order_id", "payment_sequential"]).any()
    assert not facts["fact_reviews"].duplicated(["order_id", "review_id"]).any()


@pytest.mark.parametrize(
    ("source_name", "natural_key", "fact_name"),
    [
        ("order_payments", ["order_id", "payment_sequential"], "fact_payments"),
        ("order_reviews", ["order_id", "review_id"], "fact_reviews"),
    ],
)
def test_payment_and_review_grains_reject_duplicate_natural_keys(
    source_name: str, natural_key: list[str], fact_name: str
) -> None:
    sources = _minimal_sources()
    sources[source_name] = pd.concat([sources[source_name], sources[source_name]], ignore_index=True)
    expected_message = f"{fact_name} source has 1 duplicate natural keys: {natural_key}"
    with pytest.raises(ValueError, match=re.escape(expected_message)):
        build_facts(sources, _lookups())


def test_fact_transform_is_logically_idempotent() -> None:
    first = build_facts(_minimal_sources(), _lookups())
    second = build_facts(_minimal_sources(), _lookups())
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])


def _lookups() -> dict[str, dict[str, int]]:
    return {"customer": {"customer-business-id": 1}, "product": {"product-id": 2}, "seller": {"seller-id": 3}}


def _minimal_sources() -> dict[str, pd.DataFrame]:
    orders = pd.DataFrame([{
        "order_id": "order-id", "customer_id": "customer-business-id", "order_status": "delivered",
        "order_purchase_timestamp": "2017-11-24 10:00:00", "order_approved_at": None,
        "order_delivered_carrier_date": None, "order_delivered_customer_date": None,
        "order_estimated_delivery_date": "2017-12-01 10:00:00",
    }])
    return {
        "orders": orders,
        "order_items": pd.DataFrame([{
            "order_id": "order-id", "order_item_id": 1, "product_id": "product-id", "seller_id": "seller-id",
            "shipping_limit_date": "2017-11-25 10:00:00", "price": 10.0, "freight_value": 2.0,
        }]),
        "order_payments": pd.DataFrame([{
            "order_id": "order-id", "payment_sequential": 1, "payment_type": "credit_card",
            "payment_installments": 1, "payment_value": 12.0,
        }]),
        "order_reviews": pd.DataFrame([{
            "order_id": "order-id", "review_id": "review-id", "review_score": 5,
            "review_comment_title": None, "review_comment_message": None,
            "review_creation_date": "2017-12-02 10:00:00", "review_answer_timestamp": None,
        }]),
    }
