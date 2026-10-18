-- SalesLens analytical SQL layer
-- Read-only PostgreSQL queries for the validated SalesLens star schema.
-- Important grains:
--   fact_sales    = one order item
--   fact_payments = one payment allocation
--   fact_reviews  = one review for one order
-- Facts are never joined directly without prior aggregation at order level.

-- 1. Total revenue
-- Definition: product revenue only, excluding freight.
-- Grain: fact_sales order-item rows. price is additive at this grain.
SELECT SUM(fs.price) AS total_revenue_brl
FROM public.fact_sales AS fs;

-- 2. Total orders
-- Definition: orders that have at least one sales item.
-- Grain: fact_sales repeats an order for every item, so COUNT(*) would overcount.
SELECT COUNT(DISTINCT fs.order_id) AS total_orders
FROM public.fact_sales AS fs;

-- 3. Total items sold
-- Definition: count of sales lines. Each fact_sales row is one order item.
SELECT COUNT(*) AS total_items_sold
FROM public.fact_sales AS fs;

-- 4. Average Order Value (AOV)
-- Definition: product revenue divided by distinct orders with at least one item.
-- COUNT(*) is incorrect here because it counts items, not orders.
SELECT ROUND(SUM(fs.price) / NULLIF(COUNT(DISTINCT fs.order_id), 0), 2) AS average_order_value_brl
FROM public.fact_sales AS fs;

-- 5. Total freight
-- Definition: total freight charged on order-item rows, kept separate from product revenue.
SELECT SUM(fs.freight_value) AS total_freight_brl
FROM public.fact_sales AS fs;

-- 6. Revenue by product category
-- Definition: product revenue by category. English is used when available, otherwise
-- the original Portuguese value is retained for analytical display.
-- Grain: fact_sales order-item rows joined to the product dimension.
SELECT
    COALESCE(dp.product_category_name_english, dp.product_category_name, 'not_classified') AS product_category,
    SUM(fs.price) AS revenue_brl,
    COUNT(*) AS items_sold,
    COUNT(DISTINCT fs.order_id) AS orders
FROM public.fact_sales AS fs
JOIN public.dim_product AS dp ON dp.product_key = fs.product_key
GROUP BY 1
ORDER BY revenue_brl DESC, product_category;

-- 7. Revenue by customer state
-- Definition: product revenue by the state stored on the order's customer dimension.
-- Grain: fact_sales order-item rows. customer_key identifies the Olist customer record.
SELECT
    dc.customer_state,
    SUM(fs.price) AS revenue_brl,
    COUNT(DISTINCT fs.order_id) AS orders,
    COUNT(*) AS items_sold
FROM public.fact_sales AS fs
JOIN public.dim_customer AS dc ON dc.customer_key = fs.customer_key
GROUP BY dc.customer_state
ORDER BY revenue_brl DESC, dc.customer_state;

-- 8. Average delivery time
-- Definition: calendar days from purchase to customer delivery.
-- Grain: one order. fact_sales is first collapsed by order_id so multi-item orders
-- are not given extra weight. Only orders missing either required date are excluded.
-- Limitation: dim_date stores calendar days, so time-of-day is unavailable.
WITH delivery_per_order AS (
    SELECT
        fs.order_id,
        MIN(purchase_date.calendar_date) AS purchase_date,
        MIN(delivery_date.calendar_date) AS delivered_customer_date
    FROM public.fact_sales AS fs
    JOIN public.dim_date AS purchase_date ON purchase_date.date_key = fs.purchase_date_key
    LEFT JOIN public.dim_date AS delivery_date ON delivery_date.date_key = fs.delivery_date_key
    GROUP BY fs.order_id
)
SELECT
    ROUND(AVG(delivered_customer_date - purchase_date), 2) AS average_delivery_days,
    COUNT(*) AS delivered_orders_analyzed
FROM delivery_per_order
WHERE purchase_date IS NOT NULL
  AND delivered_customer_date IS NOT NULL;

-- 9. Monthly revenue
-- Definition: product revenue by order purchase month.
-- Grain: fact_sales order-item rows; price is additive.
SELECT
    dd.year_month,
    SUM(fs.price) AS revenue_brl
FROM public.fact_sales AS fs
JOIN public.dim_date AS dd ON dd.date_key = fs.purchase_date_key
GROUP BY dd.year_month
ORDER BY dd.year_month;

-- 10. Monthly orders
-- Definition: distinct orders with at least one item, grouped by purchase month.
-- Grain: fact_sales repeats order_id, therefore DISTINCT is required.
SELECT
    dd.year_month,
    COUNT(DISTINCT fs.order_id) AS total_orders
FROM public.fact_sales AS fs
JOIN public.dim_date AS dd ON dd.date_key = fs.purchase_date_key
GROUP BY dd.year_month
ORDER BY dd.year_month;

-- 11. Top 10 categories by revenue
-- Definition: top categories by product revenue at the order-item grain.
SELECT
    COALESCE(dp.product_category_name_english, dp.product_category_name, 'not_classified') AS product_category,
    SUM(fs.price) AS revenue_brl,
    COUNT(*) AS items_sold
FROM public.fact_sales AS fs
JOIN public.dim_product AS dp ON dp.product_key = fs.product_key
GROUP BY 1
ORDER BY revenue_brl DESC, product_category
LIMIT 10;

-- 12. Top 10 sellers by revenue
-- Definition: top sellers by product revenue. This is revenue contribution, not a full
-- performance assessment because costs, returns, and margins are absent from the dataset.
-- Grain: fact_sales order-item rows.
SELECT
    ds.seller_id,
    ds.seller_state,
    SUM(fs.price) AS revenue_brl,
    COUNT(*) AS items_sold,
    COUNT(DISTINCT fs.order_id) AS orders
FROM public.fact_sales AS fs
JOIN public.dim_seller AS ds ON ds.seller_key = fs.seller_key
GROUP BY ds.seller_id, ds.seller_state
ORDER BY revenue_brl DESC, ds.seller_id
LIMIT 10;

-- 13. Revenue by payment type
-- Payment type belongs to fact_payments, whose grain is a payment allocation. A payment
-- amount is not product revenue: it can include freight and an order may use several types.
-- To avoid duplicating sales revenue, this query reports allocated payment_value only and
-- does not join fact_payments to fact_sales.
SELECT
    fp.payment_type,
    SUM(fp.payment_value) AS payment_amount_brl,
    COUNT(*) AS payment_allocations,
    COUNT(DISTINCT fp.order_id) AS orders_using_payment_type
FROM public.fact_payments AS fp
GROUP BY fp.payment_type
ORDER BY payment_amount_brl DESC, fp.payment_type;

-- 14. Average review score
-- Definition: arithmetic mean of individual review scores.
-- Grain: fact_reviews rows. Orders with multiple reviews contribute multiple review events.
SELECT
    ROUND(AVG(fr.review_score), 2) AS average_review_score,
    COUNT(*) AS total_reviews
FROM public.fact_reviews AS fr;

-- 15. Delivery time by review score
-- Delivery is first calculated once per order, then joined to individual reviews.
-- This avoids multiplying delivery rows by order items. A multi-review order contributes
-- to each score it received; this preserves the review-level grain of fact_reviews.
WITH delivery_per_order AS (
    SELECT
        fs.order_id,
        MIN(purchase_date.calendar_date) AS purchase_date,
        MIN(delivery_date.calendar_date) AS delivered_customer_date
    FROM public.fact_sales AS fs
    JOIN public.dim_date AS purchase_date ON purchase_date.date_key = fs.purchase_date_key
    LEFT JOIN public.dim_date AS delivery_date ON delivery_date.date_key = fs.delivery_date_key
    GROUP BY fs.order_id
)
SELECT
    fr.review_score,
    ROUND(AVG(dpo.delivered_customer_date - dpo.purchase_date), 2) AS average_delivery_days,
    COUNT(*) AS reviews_analyzed
FROM public.fact_reviews AS fr
JOIN delivery_per_order AS dpo ON dpo.order_id = fr.order_id
WHERE dpo.purchase_date IS NOT NULL
  AND dpo.delivered_customer_date IS NOT NULL
GROUP BY fr.review_score
ORDER BY fr.review_score;
