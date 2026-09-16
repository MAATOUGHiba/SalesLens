BEGIN;

CREATE TABLE IF NOT EXISTS public.dim_date (
    date_key INTEGER PRIMARY KEY,
    calendar_date DATE NOT NULL UNIQUE,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month_number SMALLINT NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    month_name VARCHAR(20) NOT NULL,
    year_month CHAR(7) NOT NULL,
    day_of_month SMALLINT NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS public.dim_customer (
    customer_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix INTEGER NOT NULL,
    customer_city TEXT NOT NULL,
    customer_state CHAR(2) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.dim_product (
    product_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id TEXT NOT NULL UNIQUE,
    product_category_name TEXT,
    product_category_name_english TEXT,
    product_name_length SMALLINT CHECK (product_name_length >= 0),
    product_description_length SMALLINT CHECK (product_description_length >= 0),
    product_photos_qty SMALLINT CHECK (product_photos_qty >= 0),
    product_weight_g INTEGER CHECK (product_weight_g >= 0),
    product_length_cm SMALLINT CHECK (product_length_cm >= 0),
    product_height_cm SMALLINT CHECK (product_height_cm >= 0),
    product_width_cm SMALLINT CHECK (product_width_cm >= 0)
);

CREATE TABLE IF NOT EXISTS public.dim_seller (
    seller_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    seller_id TEXT NOT NULL UNIQUE,
    seller_zip_code_prefix INTEGER NOT NULL,
    seller_city TEXT NOT NULL,
    seller_state CHAR(2) NOT NULL
);

CREATE TABLE IF NOT EXISTS public.fact_sales (
    sales_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id TEXT NOT NULL,
    order_item_id INTEGER NOT NULL CHECK (order_item_id > 0),
    customer_key BIGINT NOT NULL REFERENCES public.dim_customer(customer_key),
    product_key BIGINT NOT NULL REFERENCES public.dim_product(product_key),
    seller_key BIGINT NOT NULL REFERENCES public.dim_seller(seller_key),
    purchase_date_key INTEGER NOT NULL REFERENCES public.dim_date(date_key),
    approval_date_key INTEGER REFERENCES public.dim_date(date_key),
    shipping_limit_date_key INTEGER NOT NULL REFERENCES public.dim_date(date_key),
    carrier_date_key INTEGER REFERENCES public.dim_date(date_key),
    delivery_date_key INTEGER REFERENCES public.dim_date(date_key),
    estimated_delivery_date_key INTEGER NOT NULL REFERENCES public.dim_date(date_key),
    order_status TEXT NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    freight_value NUMERIC(12, 2) NOT NULL CHECK (freight_value >= 0),
    CONSTRAINT uq_fact_sales_order_item UNIQUE (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS public.fact_payments (
    payment_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_key BIGINT NOT NULL REFERENCES public.dim_customer(customer_key),
    purchase_date_key INTEGER NOT NULL REFERENCES public.dim_date(date_key),
    payment_sequential INTEGER NOT NULL CHECK (payment_sequential > 0),
    payment_type TEXT NOT NULL,
    payment_installments SMALLINT NOT NULL CHECK (payment_installments >= 0),
    payment_value NUMERIC(12, 2) NOT NULL CHECK (payment_value >= 0),
    CONSTRAINT uq_fact_payments_order_sequence UNIQUE (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS public.fact_reviews (
    review_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id TEXT NOT NULL,
    review_id TEXT NOT NULL,
    customer_key BIGINT NOT NULL REFERENCES public.dim_customer(customer_key),
    purchase_date_key INTEGER NOT NULL REFERENCES public.dim_date(date_key),
    review_creation_date_key INTEGER NOT NULL REFERENCES public.dim_date(date_key),
    review_answer_date_key INTEGER REFERENCES public.dim_date(date_key),
    review_score SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title TEXT,
    review_comment_message TEXT,
    CONSTRAINT uq_fact_reviews_order_review UNIQUE (order_id, review_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_order_id
    ON public.fact_sales (order_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_key
    ON public.fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product_key
    ON public.fact_sales (product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_seller_key
    ON public.fact_sales (seller_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_purchase_date_key
    ON public.fact_sales (purchase_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_payments_order_id
    ON public.fact_payments (order_id);
CREATE INDEX IF NOT EXISTS idx_fact_payments_customer_key
    ON public.fact_payments (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_payments_purchase_date_key
    ON public.fact_payments (purchase_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_reviews_order_id
    ON public.fact_reviews (order_id);
CREATE INDEX IF NOT EXISTS idx_fact_reviews_customer_key
    ON public.fact_reviews (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_reviews_creation_date_key
    ON public.fact_reviews (review_creation_date_key);

COMMIT;
