# SalesLens PostgreSQL Physical Schema

## Objective

This document describes the physical PostgreSQL implementation of the validated SalesLens logical star schema. It creates empty tables only. No Olist CSV has been loaded and no ETL has run.

The schema uses PostgreSQL `public` and is created reproducibly with `sql/01_create_schema.sql`.

## Logical Model to Physical Model

The logical design proposed a calendar, customer, product, seller, sales, payments and reviews model. The physical implementation creates those seven tables.

`dim_payment_type` was optional in the logical design. It is intentionally not created in this first physical version: `payment_type` remains a descriptive attribute in `fact_payments`. This keeps the initial model aligned with the requested seven empty tables while preserving the option to normalize payment types later.

## Tables and Grain

| Table | Grain | Primary Key | Business Key / Uniqueness |
|---|---|---|---|
| `dim_date` | One calendar date | `date_key` | `calendar_date` |
| `dim_customer` | One Olist `customer_id` | `customer_key` | `customer_id` |
| `dim_product` | One `product_id` | `product_key` | `product_id` |
| `dim_seller` | One `seller_id` | `seller_key` | `seller_id` |
| `fact_sales` | One item in one order | `sales_key` | `(order_id, order_item_id)` |
| `fact_payments` | One payment allocation in one order | `payment_key` | `(order_id, payment_sequential)` |
| `fact_reviews` | One review for one order | `review_key` | `(order_id, review_id)` |

## Dimensions

### `dim_date`

`date_key` is a calendar key intended to use the `YYYYMMDD` convention when populated by the later ETL. It has date, year, quarter, month, year-month, day and weekday attributes. It is empty in this step; calendar rows will be populated separately.

The same table supports multiple date roles without duplicate date dimensions: purchase, approval, shipping limit, carrier, delivery, estimated delivery, review creation and review answer.

### `dim_customer`

Contains Olist customer identifiers, the reusable `customer_unique_id`, postal prefix, city and state. `customer_id` is the unique source business key; `customer_unique_id` is intentionally not unique because it can recur in the processed data.

### `dim_product`

Contains product identifiers, the original Portuguese category, English category when available, and product physical attributes. Nullable product attributes reflect legitimate missing values in `products_clean.csv`.

### `dim_seller`

Contains seller identifiers, postal prefix, city and state.

## Facts and Foreign Keys

### `fact_sales`

One row represents one order item. It has foreign keys to customer, product, seller and multiple roles of `dim_date`. `price` and `freight_value` are separate `NUMERIC(12,2)` measures.

The nullable approval, carrier and delivery date keys are deliberate: those source timestamps can be absent for legitimate operational reasons.

### `fact_payments`

One row represents one payment allocation. It references customer and purchase date and keeps `order_id` as a degenerate dimension. There is no foreign key from `fact_payments` to `fact_sales`.

### `fact_reviews`

One row represents one review related to an order. It references customer, purchase date, review creation date and optional review answer date. Review comments remain nullable. Several reviews can exist for one order; any order-level score aggregation will be a later analytical rule and will not replace the original review rows.

## Types and Constraints

- Source identifiers use `TEXT`: they are opaque Olist identifiers, not PostgreSQL UUID values.
- Surrogate keys use `BIGINT GENERATED ALWAYS AS IDENTITY`.
- Calendar keys and sequence values use integer types.
- Amounts use `NUMERIC(12,2)`, not floating point, to preserve exact decimal monetary values.
- Source timestamps are represented in this first star schema through role-specific date keys. The source has no time zone, so any later retained event timestamp should use `TIMESTAMP`, not `TIMESTAMPTZ`.
- Review scores use `SMALLINT` with a `1..5` check.
- Product attributes are nullable when the processed source is nullable and have non-negative checks when the source rule is reliable.
- Unique constraints protect each validated natural fact key.

## Indexes

Indexes are created on each fact table's `order_id`, dimension foreign keys and primary purchase/review date keys. These support future joins, date filtering and order-level aggregation without adding indexes to every column.

## Double Counting Protection

Facts have different grains. An order with three items and two payment records would produce six rows if `fact_sales` and `fact_payments` were joined directly by `order_id`. Amounts would then be repeated.

For this reason, facts are not directly related. Measures are calculated from their own fact table. Cross-domain comparisons must first aggregate each fact at the order level.

## Schema Diagram

```text
                              dim_date
                   (multiple date roles)
                         /      |      \
                        /       |       \
             dim_customer    fact_sales    dim_product
                    |        order item        |
                    |      price, freight      |
                    +------------+------------+
                                 |
                            dim_seller

dim_date ---- fact_payments
                  payment allocation
                  payment_value
                       |
                  dim_customer

dim_date ---- fact_reviews
                  review per order
                  review_score
                       |
                  dim_customer

`order_id` is a degenerate dimension in all fact tables.
No fact-to-fact foreign key exists.
```

## Current State

All tables are created but empty. `dim_date` is also intentionally empty. No temporary table, Olist record, CSV import or ETL data remains in the database.
