"""Transactional PostgreSQL loading and database-side ETL validation."""

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any

import pandas as pd
import psycopg

from .transform import DIMENSION_COLUMNS, FACT_COLUMNS, build_facts


LOAD_ORDER = [
    "dim_date", "dim_customer", "dim_product", "dim_seller",
    "fact_sales", "fact_payments", "fact_reviews",
]
TABLE_COLUMNS = {**DIMENSION_COLUMNS, **FACT_COLUMNS}


def _postgres_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if hasattr(value, "item"):
        return value.item()
    return value


def copy_frame(cursor: psycopg.Cursor, table: str, frame: pd.DataFrame) -> None:
    """Bulk load one target-shaped DataFrame using PostgreSQL COPY."""
    columns = TABLE_COLUMNS[table]
    quoted_columns = ", ".join(columns)
    with cursor.copy(f"COPY public.{table} ({quoted_columns}) FROM STDIN") as copy:
        for row in frame[columns].itertuples(index=False, name=None):
            copy.write_row(tuple(_postgres_value(value) for value in row))


def fetch_lookups(cursor: psycopg.Cursor) -> dict[str, dict[str, int]]:
    """Read database-generated dimension keys for fact foreign-key mapping."""
    lookups: dict[str, dict[str, int]] = {}
    for name, business_column, technical_column in [
        ("customer", "customer_id", "customer_key"),
        ("product", "product_id", "product_key"),
        ("seller", "seller_id", "seller_key"),
    ]:
        rows = cursor.execute(
            f"SELECT {business_column}, {technical_column} FROM public.dim_{name}"
        ).fetchall()
        lookups[name] = {business_id: technical_key for business_id, technical_key in rows}
    return lookups


def _assert_database_valid(cursor: psycopg.Cursor, expected: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    """Fail the transaction if counts, natural keys, or totals do not reconcile."""
    counts: dict[str, int] = {}
    for table, source_frame in expected.items():
        count = cursor.execute(f"SELECT COUNT(*) FROM public.{table}").fetchone()[0]
        counts[table] = count
        if count != len(source_frame):
            raise ValueError(f"{table} count mismatch: database={count:,}, expected={len(source_frame):,}")

    for table, natural_keys in [
        ("fact_sales", "order_id, order_item_id"),
        ("fact_payments", "order_id, payment_sequential"),
        ("fact_reviews", "order_id, review_id"),
    ]:
        duplicates = cursor.execute(
            f"SELECT COUNT(*) FROM (SELECT {natural_keys}, COUNT(*) FROM public.{table} "
            f"GROUP BY {natural_keys} HAVING COUNT(*) > 1) duplicate_keys"
        ).fetchone()[0]
        if duplicates:
            raise ValueError(f"{table} has {duplicates:,} duplicate natural keys after load")

    foreign_key_checks = {
        "fact_sales": "customer_key IS NULL OR product_key IS NULL OR seller_key IS NULL OR "
        "purchase_date_key IS NULL OR shipping_limit_date_key IS NULL OR estimated_delivery_date_key IS NULL",
        "fact_payments": "customer_key IS NULL OR purchase_date_key IS NULL",
        "fact_reviews": "customer_key IS NULL OR purchase_date_key IS NULL OR review_creation_date_key IS NULL",
    }
    for table, condition in foreign_key_checks.items():
        null_count = cursor.execute(f"SELECT COUNT(*) FROM public.{table} WHERE {condition}").fetchone()[0]
        if null_count:
            raise ValueError(f"{table} has {null_count:,} unexpected null foreign keys")

    sums = cursor.execute(
        "SELECT "
        "(SELECT COALESCE(SUM(price), 0) FROM public.fact_sales), "
        "(SELECT COALESCE(SUM(freight_value), 0) FROM public.fact_sales), "
        "(SELECT COALESCE(SUM(payment_value), 0) FROM public.fact_payments)"
    ).fetchone()
    expected_sums = (
        Decimal(str(expected["fact_sales"]["price"].sum())).quantize(Decimal("0.01")),
        Decimal(str(expected["fact_sales"]["freight_value"].sum())).quantize(Decimal("0.01")),
        Decimal(str(expected["fact_payments"]["payment_value"].sum())).quantize(Decimal("0.01")),
    )
    if tuple(sums) != expected_sums:
        raise ValueError(f"Amount reconciliation failed: database={sums}, expected={expected_sums}")

    return {"counts": counts, "price": sums[0], "freight_value": sums[1], "payment_value": sums[2]}


def load_full_refresh(
    connection_kwargs: Mapping[str, Any],
    dimensions: Mapping[str, pd.DataFrame],
    sources: Mapping[str, pd.DataFrame],
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Atomically truncate, load, map surrogate keys, and validate the seven tables."""
    connection: psycopg.Connection | None = None
    committed = False
    try:
        connection = psycopg.connect(**connection_kwargs, autocommit=False)
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE public.fact_reviews, public.fact_payments, public.fact_sales, "
                "public.dim_seller, public.dim_product, public.dim_customer, public.dim_date "
                "RESTART IDENTITY"
            )
            for table in LOAD_ORDER[:4]:
                log(f"Loading {table}...")
                copy_frame(cursor, table, dimensions[table])
                log(f"Loaded {table}: {len(dimensions[table]):,} rows")

            facts = build_facts(sources, fetch_lookups(cursor))
            for table in LOAD_ORDER[4:]:
                log(f"Loading {table}...")
                copy_frame(cursor, table, facts[table])
                log(f"Loaded {table}: {len(facts[table]):,} rows")

            results = _assert_database_valid(cursor, {**dimensions, **facts})
            connection.commit()
            committed = True
            return results
    except Exception:
        if connection is not None and not committed:
            connection.rollback()
            log("Rollback executed")
        else:
            log("No transaction started; no rollback was needed")
        raise
    finally:
        if connection is not None:
            connection.close()
