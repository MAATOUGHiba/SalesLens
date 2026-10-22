# SalesLens Business Insights

## Executive Summary

The Olist marketplace dataset records 99,441 orders, 96,096 unique customers, 112,650 order items, 32,951 products and 3,095 sellers. Item-level product revenue totals **BRL 13,591,643.70**, with **BRL 2,251,909.54** in freight recorded separately. The product-value average order value is **BRL 137.75** across the 98,666 orders that contain at least one item.

Observed activity is concentrated in customer state SP and a small set of leading product categories. November 2017 is the highest observed month for product revenue. Delivery takes a mean of 12.56 days among orders with usable delivery dates; lower review scores are associated with longer delivery times. These are descriptive findings for prioritizing analysis and operational review, not evidence of causal effects or profitability.

## Key Business Insights

### 1. A substantial marketplace with a clear gap between all orders and itemized orders

**Finding and evidence:** The dataset contains 99,441 orders and 112,650 items. The sales analysis includes 98,666 distinct orders because 775 orders have no order-item line. The item-based sales fact therefore covers fewer orders than the orders table. Product revenue is BRL 13,591,643.70; freight is BRL 2,251,909.54.

**Business interpretation:** Item and product metrics describe orders with item lines. They should not be presented as covering every order record.

**Recommendation:** Report the total order-table count alongside item-based sales order counts, and investigate the 775 itemless orders in operational reporting before interpreting them as missing sales.

### 2. Product revenue is concentrated in leading categories, while volume and value rankings differ

**Finding and evidence:** `health_beauty` leads product revenue at **BRL 1,258,681.34** from 9,670 items. `bed_bath_table` has the greatest item volume at **11,115 items**, generating **BRL 1,036,988.68**. The respective average item prices are BRL 130.16 and BRL 93.30.

**Business interpretation:** Category importance depends on whether the lens is item volume or product revenue; the highest-volume category is not the top revenue category. These figures say nothing about category profitability.

**Recommendation:** Review category performance using both item volume and product revenue, then add cost, returns and availability data before making assortment or promotion decisions.

### 3. November 2017 was the peak observed product-revenue month

**Finding and evidence:** November 2017 recorded **BRL 1,010,271.37** in product revenue across **7,451** orders; it is the maximum month in the EDA purchase-month series.

**Business interpretation:** This period is a useful candidate for examining campaign, category and operating activity. It does not establish a recurring seasonal peak.

**Recommendation:** Compare the month with campaign calendars and operational records, and validate any future seasonal planning against longer, complete periods.

### 4. Observed customer activity is concentrated in São Paulo state

**Finding and evidence:** SP accounts for **41,375 itemized orders** and **BRL 5,202,955.05** of product revenue, the largest state totals in the EDA. RJ follows with 12,762 orders and BRL 1,824,092.67.

**Business interpretation:** The observed sales base is geographically concentrated. Customer state is a description of current activity, not a measure of market potential or unmet demand.

**Recommendation:** Use state as a reporting and service-planning slice. Evaluate expansion opportunities only with additional market-size, delivery-cost and customer-acquisition evidence.

### 5. Credit cards lead recorded payment value and order coverage

**Finding and evidence:** Credit-card allocations total **BRL 12,542,084.19** across **76,505 distinct orders** and 76,795 payment records. Boleto totals BRL 2,869,361.27 across 19,784 orders.

**Business interpretation:** Credit card is the largest recorded payment type in this dataset. Payment records are allocations, not orders: payment totals can reflect multiple rows or methods for an order and are distinct from product revenue and freight.

**Recommendation:** Monitor payment mix using both allocated value and distinct orders by type. Keep payment analysis separate from sales totals, and investigate the recorded gap between total payment value and item revenue plus freight through finance reconciliation rather than assuming they are interchangeable.

### 6. Typical delivery is faster than the average, with a long-delay tail

**Finding and evidence:** For **96,476** orders with both purchase and customer-delivery timestamps, mean delivery time is **12.56 days** and median is **10.22 days**. The observed range is 0.53 to 209.63 days.

**Business interpretation:** The mean exceeding the median, together with the long maximum, indicates that a smaller number of long deliveries lifts the average. The dataset does not identify the operational causes.

**Recommendation:** Track median and upper-tail delivery time alongside the mean, and review delayed orders by available operational dimensions before changing carrier or fulfillment processes.

### 7. One-star reviews are associated with longer delivery times

**Finding and evidence:** The EDA reports a correlation of **-0.334** between delivery days and mean review score per order. Orders with a one-star score averaged **21.34 delivery days**, compared with **10.68 days** for five-star orders. The overall review mean is **4.09** across 99,224 review records.

**Business interpretation:** Longer delivery times and lower scores move together in the observed data. This association does not show that delivery time alone causes low ratings; product quality, expectations, customer service and other factors may also matter.

**Recommendation:** Prioritize a focused review of long-delivery, low-score orders and consider delivery communication as one part of that investigation. Track review and delivery measures together, while assessing other potential contributors.

## Operational Recommendations

1. **Establish consistent KPI reporting.** Publish item-based product revenue, freight, payment value, and all-order versus itemized-order counts as separate measures with their grains shown.
2. **Investigate service outliers.** Use median and upper-tail delivery time to identify delayed orders, then compare available order, seller and customer dimensions. Pair this with review evidence without assigning causation.
3. **Review category and geographic mix.** Track revenue and item volume together by category and state; avoid treating current activity as evidence of margin or growth potential.
4. **Reconcile payment and sales measures.** Review the differences between allocation-level payment totals and item-level product-plus-freight totals with a clearly defined financial reconciliation process.
5. **Validate the November peak.** Check the November 2017 result against campaign and operational records before using it to inform recurring plans.

## Limitations and Caveats

- **Association is not causation.** The negative delivery/review relationship is observational. It does not isolate delivery time from product, service, expectation or other factors.
- **Coverage is incomplete at period edges.** Purchase timestamps run from 2016-09-04 through 2018-10-17. The EDA notes incomplete edge months and a roughly two-year window, so monthly peaks do not establish seasonality or long-term growth.
- **Missing delivery timestamps matter.** The delivery calculation excludes orders without a customer-delivery timestamp; the cleaning report records 2,965 missing values in that field. Its results describe only orders with usable purchase and delivery dates.
- **The orders and sales grains differ.** There are 99,441 order records, but only 98,666 distinct orders in the item-based sales fact; the ETL documentation attributes the 775-order difference to orders without item lines.
- **Multiple rows occur within orders.** An order can have multiple item lines, payment allocations and review rows. Summing measures after direct fact-to-fact joins can multiply values. The EDA averages multiple review scores per order for its delivery association; SQL preserves review-level results for score breakdowns.
- **Payment totals are not revenue.** `payment_value` is recorded at payment-allocation grain and may represent several allocations or methods per order. It is distinct from item price and freight. The ETL reconciliation totals are BRL 16,008,872.12 in payment value, BRL 13,591,643.70 in product revenue and BRL 2,251,909.54 in freight; these should not be combined or substituted without an explicit financial definition.
- **Profit and margin cannot be calculated.** Product cost data is unavailable; the documented dataset also does not provide explicit tax or discount measures. Product revenue is not profit, margin or a complete measure of seller performance.
- **SQL results are query specifications, not execution evidence here.** `sql/02_analytics.sql` defines the analytics and grain-safe calculations, but the repository contains no saved result set. The ETL documentation provides reconciliation totals for sales and payments, not executed delivery-query results.

## Methodology and KPI Definitions

| KPI | Definition used in this report | Grain and caveat |
|---|---|---|
| **Product revenue** | Sum of `order_items.price` / `fact_sales.price`. Verified total: **BRL 13,591,643.70**. | One row per item; excludes freight and is not profit. |
| **Freight** | Sum of `order_items.freight_value` / `fact_sales.freight_value`. Verified total: **BRL 2,251,909.54**. | One row per item. Report separately from product revenue. |
| **Payment value** | Sum of `order_payments.payment_value` / `fact_payments.payment_value`. ETL reconciliation: **BRL 16,008,872.12**. | One row per payment allocation; not product revenue, and not directly additive to sales facts after a join. |
| **Average order value (AOV)** | Product revenue divided by distinct orders with at least one item: `SUM(price) / COUNT(DISTINCT order_id)`. Verified notebook value: **BRL 137.75**. | Item-based orders only; the EDA groups item prices by order before averaging. |
| **Order counts** | Count distinct `order_id` at the relevant grain. | Orders table: **99,441** total; sales fact: **98,666** with item lines. Never use item row count as an order count. |
| **Delivery time** | Notebook: elapsed time between purchase and customer-delivery timestamps, converted to days. SQL: difference between the corresponding calendar dates in `dim_date`. | The notebook uses all 96,476 orders with both timestamps. SQL derives one row per order from `fact_sales`, so it can only include orders with item lines, and date-only keys discard time-of-day. The SQL query does not have a saved result in the repository; its exact count and average cannot be confirmed here. |
| **Review score** | Arithmetic mean of individual review scores for the overall review KPI; for EDA delivery association, review scores are first averaged per order. | There are 99,224 review records and 547 orders with multiple review rows. Make the review grain explicit when comparing or aggregating. |

**Delivery-average reconciliation:** The notebook reports **12.56 days** from timestamp differences on **96,476** delivered orders. SQL query 8 instead averages calendar-date differences after collapsing `fact_sales` to one row per order. The ETL documentation states that the sales fact has **98,666** distinct itemized orders, versus **99,441** orders in the source; consequently, SQL excludes source orders without item lines. It also uses calendar dates, so an order’s elapsed timestamp duration is not preserved. These population and precision differences explain why the methods can produce different averages. The repository does not include SQL execution results, so the reported approximate SQL average of **12.50 days** and its actual analyzed-order count remain unverified and require manual verification against the database.

**Evidence basis:** `notebooks/03_eda.ipynb` recorded outputs, `docs/data_cleaning_report.md`, `docs/star_schema_design.md`, `docs/etl_design.md`, and the definitions and grain safeguards in `sql/02_analytics.sql`. Figures are rounded only where shown as rounded.
