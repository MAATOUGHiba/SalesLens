# SalesLens ETL Design

## 1. Objective

This document defines the ETL design that will load cleaned Olist CSV files from `data/processed/` into the empty PostgreSQL SalesLens star schema. It is a design document only: no ETL code, CSV loading, PostgreSQL insertion, or schema modification is performed in this step.

The ETL must be reproducible, transactional, observable, and safe to rerun. It must preserve the validated grain of each target fact table.

## 2. Scope and Existing Transformations

The ETL consumes processed CSV files only. `data/raw/` is immutable and must never be read as an ETL source.

The cleaning layer has already:

- removed exact duplicates from geolocation;
- converted source date columns to datetime during Python processing before CSV export;
- kept legitimate missing operational dates and review comments;
- added `product_category_name_english` while preserving `product_category_name`.

The ETL must parse date fields explicitly when reading processed CSV files because CSV serialization does not preserve Python datetime types. It must not repeat or alter cleaning decisions.

## 3. Target PostgreSQL Tables

| Target table | Grain | Status before ETL |
|---|---|---|
| `dim_date` | One calendar date | Empty |
| `dim_customer` | One Olist `customer_id` | Empty |
| `dim_product` | One `product_id` | Empty |
| `dim_seller` | One `seller_id` | Empty |
| `fact_sales` | One item in one order | Empty |
| `fact_payments` | One payment allocation in one order | Empty |
| `fact_reviews` | One review for one order | Empty |

`order_id` is a degenerate dimension stored in all three facts. There is no physical relationship between facts.

## 4. Source to Target Matrix

| Target | Processed source(s) | Main source fields | ETL responsibility |
|---|---|---|---|
| `dim_date` | `orders_clean.csv`, `order_items_clean.csv`, `order_reviews_clean.csv` | All date/timestamp columns used by the facts | Parse, normalize to calendar days, derive calendar attributes and generate `YYYYMMDD` keys. |
| `dim_customer` | `customers_clean.csv` | `customer_id`, `customer_unique_id`, postal prefix, city, state | Insert one row per unique `customer_id`. |
| `dim_product` | `products_clean.csv` | Product ID, Portuguese and English categories, text lengths, photos, weight, dimensions | Rename source typo fields `*_lenght` to physical target fields `*_length`; preserve nulls. |
| `dim_seller` | `sellers_clean.csv` | Seller ID, postal prefix, city, state | Insert one row per unique `seller_id`. |
| `fact_sales` | `order_items_clean.csv` + `orders_clean.csv` + dimensions | Item identifiers, product, seller, price, freight, order customer/status/dates | Join items to orders on `order_id`, then resolve dimension surrogate keys and date keys. |
| `fact_payments` | `order_payments_clean.csv` + `orders_clean.csv` + dimensions | Payment sequence/type/installments/value, order customer and purchase date | Join payments to orders only, then resolve customer and purchase date keys. |
| `fact_reviews` | `order_reviews_clean.csv` + `orders_clean.csv` + dimensions | Review ID, score, comments, review dates, order customer and purchase date | Join reviews to orders only, then resolve customer and date keys. |

The ETL will not use `geolocation_clean.csv` or `product_category_translation_clean.csv` in this first physical model. Geography is intentionally deferred, and English product categories are already available in `products_clean.csv`.

## 5. Load Order

The target loading order is:

```text
1. dim_date
2. dim_customer
3. dim_product
4. dim_seller
5. fact_sales
6. fact_payments
7. fact_reviews
```

Dimensions must be loaded before facts because fact foreign keys reference dimension surrogate keys. A fact loaded first would not have valid `customer_key`, `product_key`, `seller_key`, or `date_key` values.

The three facts are independent after dimensions exist. The proposed order places sales first because it is the main business fact, but facts must never be joined to each other during loading.

## 6. Surrogate-Key Mapping

Source files use Olist business keys; PostgreSQL dimensions use technical surrogate keys.

```text
customer_id -> dim_customer.customer_id -> dim_customer.customer_key -> fact customer_key
product_id  -> dim_product.product_id   -> dim_product.product_key  -> fact_sales.product_key
seller_id   -> dim_seller.seller_id     -> dim_seller.seller_key    -> fact_sales.seller_key
calendar day -> dim_date.calendar_date  -> dim_date.date_key        -> fact date-role key
```

The ETL loads dimensions, retrieves lookup mappings from PostgreSQL, then joins those mappings to the prepared fact DataFrames before loading facts. Olist IDs must remain business identifiers; they must not replace surrogate keys because dimensions may later evolve while facts need stable dimensional references.

The proposed `date_key` convention is `YYYYMMDD`. For example, `2017-11-24` becomes integer `20171124`. It is readable, sortable in chronological order, and maps directly to `dim_date.calendar_date`.

## 7. dim_date Design

### Date roles and real source range

| Source | Date column | Non-null values | Null values | Minimum day | Maximum day |
|---|---|---:|---:|---|---|
| `orders_clean.csv` | `order_purchase_timestamp` | 99 441 | 0 | 2016-09-04 | 2018-10-17 |
| `orders_clean.csv` | `order_approved_at` | 99 281 | 160 | 2016-09-15 | 2018-09-03 |
| `orders_clean.csv` | `order_delivered_carrier_date` | 97 658 | 1 783 | 2016-10-08 | 2018-09-11 |
| `orders_clean.csv` | `order_delivered_customer_date` | 96 476 | 2 965 | 2016-10-11 | 2018-10-17 |
| `orders_clean.csv` | `order_estimated_delivery_date` | 99 441 | 0 | 2016-09-30 | 2018-11-12 |
| `order_items_clean.csv` | `shipping_limit_date` | 112 650 | 0 | 2016-09-19 | 2020-04-09 |
| `order_reviews_clean.csv` | `review_creation_date` | 99 224 | 0 | 2016-10-02 | 2018-08-31 |
| `order_reviews_clean.csv` | `review_answer_timestamp` | 99 224 | 0 | 2016-10-07 | 2018-10-29 |

The dimension range must therefore be `2016-09-04` through `2020-04-09`, inclusive: 1,314 calendar rows. The 2020 maximum comes from `shipping_limit_date`, not from a 2020 order.

### Generation

The ETL will create one daily range using `pandas.date_range(min_date, max_date, freq='D')` and derive:

- `date_key` = `YYYYMMDD` integer;
- `calendar_date`;
- year, quarter, month number, month name, year-month;
- day of month, ISO day of week, day name, weekend flag.

Timestamp fields are normalized to their calendar day before key mapping. Time-of-day is not retained in the current physical star schema. Missing optional timestamps map to SQL `NULL`, not to an artificial date.

## 8. Dimension Transformations

### dim_customer

- Source: `customers_clean.csv`.
- Business key: `customer_id`; it is unique in the processed source.
- Technical key: generated by PostgreSQL identity column.
- Columns: customer business ID, reusable customer ID, postal prefix, city and state.
- Duplicates: fail ETL validation if `customer_id` is duplicated; do not deduplicate silently.
- Missing values: the current source has none in required customer columns. No unknown customer will be created.
- Fact mapping: orders provide `customer_id`; the ETL resolves it to `customer_key` through `dim_customer`.

### dim_product

- Source: `products_clean.csv`.
- Business key: `product_id`; it is unique.
- Technical key: generated by PostgreSQL identity column.
- `product_name_lenght` and `product_description_lenght` are renamed only in the ETL projection to the physical columns `product_name_length` and `product_description_length`.
- Portuguese category and English category are both preserved. The 623 absent English translations remain SQL `NULL`; they are not replaced with an artificial category.
- Missing physical attributes remain `NULL`, as allowed by `dim_product`.
- Fact mapping: `order_items_clean.csv.product_id` resolves to `product_key`.

### dim_seller

- Source: `sellers_clean.csv`.
- Business key: `seller_id`; it is unique.
- Technical key: generated by PostgreSQL identity column.
- Columns: seller business ID, postal prefix, city, state.
- Missing values: current required seller fields are complete. No unknown seller will be created.
- Fact mapping: `order_items_clean.csv.seller_id` resolves to `seller_key`.

## 9. Fact Transformations

### fact_sales

**Required grain:** one row per order item.

```text
order_items_clean
       + orders_clean on order_id
       + dim_customer lookup on customer_id
       + dim_product lookup on product_id
       + dim_seller lookup on seller_id
       + dim_date lookup for each date role
       -> fact_sales
```

`order_items_clean.csv` is the driving table. The ETL performs exactly one many-to-one join to `orders_clean.csv` on `order_id`; orders are unique, so this cannot multiply item rows. Expected output: 112,650 rows, with natural-key uniqueness on `(order_id, order_item_id)`.

Target mapping:

| fact_sales target | Source / rule |
|---|---|
| `order_id`, `order_item_id` | order items |
| `customer_key` | orders `customer_id` -> customer lookup |
| `product_key` | item `product_id` -> product lookup |
| `seller_key` | item `seller_id` -> seller lookup |
| `purchase_date_key` | date portion of `order_purchase_timestamp` |
| `approval_date_key` | date portion of `order_approved_at`, nullable |
| `shipping_limit_date_key` | date portion of `shipping_limit_date` |
| `carrier_date_key` | date portion of `order_delivered_carrier_date`, nullable |
| `delivery_date_key` | date portion of `order_delivered_customer_date`, nullable |
| `estimated_delivery_date_key` | date portion of `order_estimated_delivery_date` |
| `order_status` | orders |
| `price`, `freight_value` | order items, loaded separately as numeric values |

All surrogate/date key lookups must resolve. A non-null source identifier or mandatory date failing to resolve is a hard ETL error and triggers rollback.

### fact_payments

**Required grain:** one row per payment allocation.

```text
order_payments_clean
       + orders_clean on order_id
       + dim_customer lookup
       + dim_date purchase lookup
       -> fact_payments
```

Payments join only to the unique orders table. They must never join to `fact_sales` or order items during ETL. Expected output: 103,886 rows, unique on `(order_id, payment_sequential)`.

The ETL loads `order_id`, payment sequence, type, installments and payment value from payments. It derives `customer_key` and `purchase_date_key` through orders. `purchase_date_key` is explicitly the order purchase date; there is no payment timestamp in the source.

### fact_reviews

**Required grain:** one row per review for an order.

```text
order_reviews_clean
       + orders_clean on order_id
       + dim_customer lookup
       + dim_date lookups
       -> fact_reviews
```

Reviews join only to the unique orders table. Expected output: 99,224 rows, unique on `(order_id, review_id)`. The ETL preserves all review rows; it does not average, keep the last review, or otherwise merge reviews. A future order-level analysis may calculate a score aggregation separately.

`review_answer_date_key` remains `NULL` only when the answer timestamp is absent. Review title and message remain `NULL` when absent in the source.

## 10. NULL Policy

| Case | ETL policy |
|---|---|
| Approval, carrier, delivery timestamps absent | Map corresponding optional fact date key to SQL `NULL`. |
| English product category absent | Preserve SQL `NULL`. |
| Product physical attribute absent | Preserve SQL `NULL`. |
| Review title or message absent | Preserve SQL `NULL`. |
| Required source business ID missing or unresolved | Fail validation and roll back; do not invent an unknown member without an approved business rule. |
| Required source date missing or unresolved | Fail validation and roll back. |

No `Unknown`, zero, artificial date, or replacement text is introduced in this first ETL because the cleaned data does not require it to maintain referential integrity.

## 11. Quality Controls After Load

### Volumes

| Target / source basis | Expected rows |
|---|---:|
| `dim_customer` / customers | 99 441 |
| `dim_product` / products | 32 951 |
| `dim_seller` / sellers | 3 095 |
| `fact_sales` / order items | 112 650 |
| `fact_payments` / payments | 103 886 |
| `fact_reviews` / reviews | 99 224 |
| `dim_date` / date range | 1 314 |

### Uniqueness

- `fact_sales`: `COUNT(*) = COUNT(DISTINCT (order_id, order_item_id))`.
- `fact_payments`: `COUNT(*) = COUNT(DISTINCT (order_id, payment_sequential))`.
- `fact_reviews`: `COUNT(*) = COUNT(DISTINCT (order_id, review_id))`.

### Referential Integrity

Foreign keys enforce most referential integrity. The ETL must also report unresolved lookup counts before attempting the load. All required customer, product, seller and mandatory date lookups must have zero unresolved values.

### Reconciliation with EDA

Post-load reconciliation must compare:

| Measure | Expected value from processed data / EDA |
|---|---:|
| `SUM(fact_sales.price)` | BRL 13,591,643.70 |
| `SUM(fact_sales.freight_value)` | BRL 2,251,909.54 |
| `SUM(fact_payments.payment_value)` | BRL 16,008,872.12 |
| Distinct `fact_sales.order_id` | 98,666 |
| Distinct orders source | 99,441 |

The last two numbers differ by design: 775 orders have no order-item line, so they cannot appear in `fact_sales`. This is not a fact-loading failure. Payments and reviews can still refer to such orders through their own facts.

Any reconciliation difference outside the documented grain difference must fail the ETL validation and be investigated.

## 12. Idempotence and Transactions

For this local portfolio, the recommended strategy is a full refresh:

1. Open one PostgreSQL transaction.
2. `TRUNCATE` all seven star tables together, using `RESTART IDENTITY` and a dependency-safe order or `CASCADE` only when the exact target list is explicit.
3. Load dimensions.
4. Resolve dimension keys and load facts.
5. Run database-side validation queries.
6. Commit only when all loads and validations pass; otherwise roll back.

The preferred implementation should explicitly list only SalesLens tables in the truncation command. Running ETL twice therefore recreates the same database contents without duplicate rows. Incremental / CDC logic is unnecessary for these stable public CSV snapshots.

Note: a PostgreSQL `TRUNCATE` inside a transaction is reversible until commit, which protects this first full-refresh approach from a partially loaded state.

## 13. Logging

The future runner should emit concise structured logs containing:

- ETL start time and source directory;
- source rows read per CSV;
- date range selected for `dim_date`;
- rows inserted per dimension and fact;
- unresolved lookup counts before load;
- validation results and reconciliation totals;
- completion time and duration;
- exception type and message before rollback when a failure occurs.

Secrets, connection strings containing passwords, and row-level customer data must never be logged.

## 14. Performance Strategy

The largest target is `fact_sales` at about 112,650 rows. The full set is modest for a local PostgreSQL project.

| Option | Assessment |
|---|---|
| Individual inserts | Too slow and unnecessarily chatty. |
| Batched `executemany` / `execute_values` | Simple and adequate for these volumes. |
| PostgreSQL `COPY` from in-memory CSV buffers | Recommended: fast, standard PostgreSQL bulk load, and still simple once DataFrames are prepared. |
| Staging schemas and external orchestration | Unnecessary for this portfolio scale. |

Recommended approach: use pandas for reading, parsing dates and joining lookup maps; use psycopg version 3 and `COPY` to bulk-load prepared DataFrames directly into the seven target tables inside one transaction.

## 15. Proposed Python Architecture

The implementation should be created only after this design is approved:

```text
src/
└── etl/
    ├── __init__.py
    ├── config.py
    ├── extract.py
    ├── transform.py
    ├── load.py
    └── run_etl.py
```

| Module | Responsibility |
|---|---|
| `config.py` | Load local database configuration from environment variables; never hardcode credentials. |
| `extract.py` | Read only `data/processed/` CSV files and parse declared date columns. |
| `transform.py` | Build `dim_date`, prepare target-shaped DataFrames and resolve surrogate-key mappings. |
| `load.py` | Own the PostgreSQL transaction, explicit truncate, bulk `COPY`, validation SQL and rollback. |
| `run_etl.py` | Orchestrate extract, transform, load and logging. |

This separation is intentionally small: it distinguishes data access, transformations and database writes without creating a framework.

## 16. Process Diagram

```text
data/processed
       |
       v
     Extract
       |
       v
    Transform
       |
       +--> build dim_date
       +--> map business keys to surrogate keys
       +--> validate fact grain and NULL policy
       |
       v
      Load
       |
       v
   PostgreSQL
       |
       +--> dimensions
       +--> facts
```

## 17. Limits and Decisions Pending Approval

- The ETL will retain only date keys, not timestamp time-of-day, because that is the current physical schema. Retaining event timestamps would require a deliberate schema change.
- `payment_type` remains in `fact_payments`; no payment-type dimension is loaded in the first implementation.
- Multiple review rows remain multiple rows in `fact_reviews`. Any order-level review rule belongs to later analytics, not the load.
- No geography dimension is loaded until a postal-code aggregation rule is approved.
- The full-refresh strategy is appropriate for this portfolio snapshot but would need review for a production incremental pipeline.
- The ETL should load the seven designed tables only; it must not load raw data, create business tables, or introduce an unknown dimension member without a documented rule.

## 18. Implementation

The implemented ETL follows this design without changing the PostgreSQL schema or either CSV layer.

### Files

```text
src/etl/
    __init__.py    Package marker
    config.py      Loads local paths and PostgreSQL settings from .env
    extract.py     Reads the nine processed CSV files and parses declared dates
    transform.py   Builds dimensions, facts, date keys, and verifies source grain
    load.py        Runs transactional COPY loading, key mapping, and SQL validation
    run_etl.py     Orchestrates the complete pipeline and emits concise logs
tests/test_etl_transform.py
    Focused tests for date keys, technical-key mapping, fact grain, and deterministic transforms
```

### Run command

From the project root with Docker Desktop and the SalesLens PostgreSQL container running:

```powershell
.\.venv\Scripts\python.exe -m src.etl.run_etl
```

The runner reads `data/processed/` only. It loads credentials from the ignored local `.env` file and never prints the password.

### Dependencies

- `pandas`: CSV extraction, explicit date parsing, and DataFrame transformations.
- `psycopg[binary]`: PostgreSQL connection and efficient `COPY` bulk loading.
- `python-dotenv`: local `.env` loading without hardcoded credentials.
- `pytest`: focused automated transformation tests.

### Transaction and idempotence

One PostgreSQL transaction explicitly truncates only the seven SalesLens star-schema tables with `RESTART IDENTITY`, loads dimensions first, obtains their database-generated surrogate keys, then bulk-loads facts using `COPY`. Database-side validations run before `COMMIT`. Any exception triggers rollback, leaving the preceding committed state intact. A second successful run recreates the same contents instead of adding duplicates.

### Implemented validation

The loader checks source-to-target row counts, natural-key uniqueness for all facts, required foreign-key values, and reconciliation of product revenue, freight, and payment totals. PostgreSQL foreign keys also reject orphan technical keys during loading.
