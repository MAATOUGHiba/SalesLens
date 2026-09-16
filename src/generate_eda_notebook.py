from __future__ import annotations

from pathlib import Path

import nbformat as nbf


NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "03_eda.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text)


def code(text: str):
    return nbf.v4.new_code_cell(text)


def build_notebook():
    return nbf.v4.new_notebook(
        cells=[
            md("# SalesLens - Exploratory Data Analysis"),
            md(
                "This notebook answers business questions with the processed Olist data. "
                "It creates temporary analytical tables in memory only; it does not modify `data/raw/` or `data/processed/`."
            ),
            md("## 1. Business Questions\n"
               "- How large is the marketplace in orders, customers, products, sellers, items, product revenue, and freight?\n"
               "- How do orders and product revenue evolve over time?\n"
               "- Which categories, states, payment types, and sellers account for the largest observed activity?\n"
               "- What delivery times are observed, and how are they associated with review scores?\n"
               "- Which patterns require cautious interpretation because of data granularity or incomplete coverage?"),
            md("## 2. Load Processed Data\n"
               "Question: Which processed datasets and fields are available for analysis?\n\n"
               "Dates are explicitly parsed on reload because CSV files store them as text."),
            code(
                "from pathlib import Path\n"
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n"
                "import seaborn as sns\n\n"
                "sns.set_theme(style='whitegrid', palette='deep')\n"
                "project_root = Path.cwd().resolve().parent if Path.cwd().name == 'notebooks' else Path.cwd().resolve()\n"
                "processed_dir = project_root / 'data' / 'processed'\n\n"
                "orders = pd.read_csv(processed_dir / 'orders_clean.csv', parse_dates=['order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date'])\n"
                "items = pd.read_csv(processed_dir / 'order_items_clean.csv', parse_dates=['shipping_limit_date'])\n"
                "products = pd.read_csv(processed_dir / 'products_clean.csv')\n"
                "customers = pd.read_csv(processed_dir / 'customers_clean.csv')\n"
                "payments = pd.read_csv(processed_dir / 'order_payments_clean.csv')\n"
                "reviews = pd.read_csv(processed_dir / 'order_reviews_clean.csv', parse_dates=['review_creation_date', 'review_answer_timestamp'])\n"
                "sellers = pd.read_csv(processed_dir / 'sellers_clean.csv')\n\n"
                "{name: df.shape for name, df in {'orders': orders, 'items': items, 'products': products, 'customers': customers, 'payments': payments, 'reviews': reviews, 'sellers': sellers}.items()}"
            ),
            md("### Analytical working tables\n"
               "`item_fact` has one row per order item. It is appropriate for product revenue, freight, category volume, and seller volume. "
               "It must not be used to count orders without `nunique(order_id)`."),
            code(
                "item_fact = (items\n"
                "    .merge(orders[['order_id', 'customer_id', 'order_purchase_timestamp', 'order_delivered_customer_date']], on='order_id', how='inner')\n"
                "    .merge(customers[['customer_id', 'customer_unique_id', 'customer_state']], on='customer_id', how='left')\n"
                "    .merge(products[['product_id', 'product_category_name', 'product_category_name_english']], on='product_id', how='left')\n"
                ")\n"
                "item_fact['category_display'] = item_fact['product_category_name_english'].fillna(item_fact['product_category_name']).fillna('Missing category')\n"
                "item_fact['purchase_month'] = item_fact['order_purchase_timestamp'].dt.to_period('M').astype(str)\n"
                "item_fact.shape"
            ),
            md("## 3. Sales Overview\n"
               "Question: What is the observed commercial scale of the marketplace?\n\n"
               "Definitions: product revenue is `sum(order_items.price)`; freight is `sum(order_items.freight_value)`; average basket is the mean product-value total per order with at least one item. Payment value is deliberately not used as revenue because it is a separate payment-level measure."),
            code(
                "order_product_totals = items.groupby('order_id', as_index=False)['price'].sum()\n"
                "kpis = pd.Series({\n"
                "    'Orders': orders['order_id'].nunique(),\n"
                "    'Unique customers': customers['customer_unique_id'].nunique(),\n"
                "    'Products': products['product_id'].nunique(),\n"
                "    'Sellers': sellers['seller_id'].nunique(),\n"
                "    'Items sold': len(items),\n"
                "    'Product revenue (BRL)': items['price'].sum(),\n"
                "    'Freight value (BRL)': items['freight_value'].sum(),\n"
                "    'Average basket - product value (BRL)': order_product_totals['price'].mean(),\n"
                "})\n"
                "kpis.to_frame('Value')"
            ),
            md("Interpretation: product revenue and freight are separate components. `payment_value` can differ from either because payments may include several payment records per order."),
            md("## 4. Sales Over Time\n"
               "Question: How do order activity, product revenue, and average basket evolve by purchase month?\n\n"
               "The calculation uses `order_purchase_timestamp` and item-level product prices. The partial months at the beginning and end of the dataset must not be treated as normal full months."),
            code(
                "monthly = item_fact.groupby('purchase_month').agg(\n"
                "    orders=('order_id', 'nunique'),\n"
                "    product_revenue=('price', 'sum')\n"
                ").reset_index()\n"
                "monthly['average_basket'] = monthly['product_revenue'] / monthly['orders']\n"
                "monthly['purchase_month'] = pd.to_datetime(monthly['purchase_month'])\n"
                "monthly.head()"
            ),
            code(
                "fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)\n"
                "sns.lineplot(data=monthly, x='purchase_month', y='orders', marker='o', ax=axes[0], color='#0F6B78')\n"
                "axes[0].set(title='Orders by Purchase Month', xlabel='', ylabel='Unique orders')\n"
                "sns.lineplot(data=monthly, x='purchase_month', y='product_revenue', marker='o', ax=axes[1], color='#C06C3E')\n"
                "axes[1].set(title='Product Revenue by Purchase Month', xlabel='Purchase month', ylabel='BRL')\n"
                "plt.tight_layout()\n"
                "plt.show()\n\n"
                "monthly.loc[monthly['product_revenue'].idxmax()].to_frame().T"
            ),
            md("Limit: this period covers roughly two years, with incomplete edge months. It supports a trend description, not a confirmed seasonal pattern."),
            md("## 5. Product Analysis\n"
               "Question: Which product categories generate the most item volume and product revenue, and why can the rankings differ?\n\n"
               "Category labels use English when available, otherwise the original Portuguese category is shown. The original value remains unchanged in `products_clean.csv`."),
            code(
                "category_summary = item_fact.groupby('category_display').agg(\n"
                "    items_sold=('order_item_id', 'size'),\n"
                "    product_revenue=('price', 'sum'),\n"
                "    average_item_price=('price', 'mean')\n"
                ").sort_values('product_revenue', ascending=False)\n"
                "category_summary.head(10)"
            ),
            code(
                "top_volume = category_summary.nlargest(10, 'items_sold').sort_values('items_sold')\n"
                "top_revenue = category_summary.nlargest(10, 'product_revenue').sort_values('product_revenue')\n"
                "fig, axes = plt.subplots(1, 2, figsize=(16, 7))\n"
                "sns.barplot(data=top_volume.reset_index(), x='items_sold', y='category_display', ax=axes[0], color='#49796B')\n"
                "axes[0].set(title='Top Categories by Item Volume', xlabel='Items sold', ylabel='Category')\n"
                "sns.barplot(data=top_revenue.reset_index(), x='product_revenue', y='category_display', ax=axes[1], color='#C06C3E')\n"
                "axes[1].set(title='Top Categories by Product Revenue', xlabel='Product revenue (BRL)', ylabel='Category')\n"
                "plt.tight_layout()\n"
                "plt.show()"
            ),
            md("Interpretation: volume and revenue can diverge because categories have different average item prices. A category can sell fewer items while generating more revenue."),
            md("## 6. Customer Analysis\n"
               "Question: Which customer states account for the largest number of observed orders and product revenue?\n\n"
               "The state comes from the customer record associated with each order. This is a location distribution, not a measure of market potential."),
            code(
                "state_summary = item_fact.groupby('customer_state').agg(\n"
                "    customers=('customer_unique_id', 'nunique'),\n"
                "    orders=('order_id', 'nunique'),\n"
                "    product_revenue=('price', 'sum')\n"
                ").sort_values('product_revenue', ascending=False)\n"
                "state_summary.head(10)"
            ),
            code(
                "top_states = state_summary.head(10).sort_values('product_revenue')\n"
                "plt.figure(figsize=(10, 6))\n"
                "sns.barplot(data=top_states.reset_index(), x='product_revenue', y='customer_state', color='#345995')\n"
                "plt.title('Top Customer States by Product Revenue')\n"
                "plt.xlabel('Product revenue (BRL)')\n"
                "plt.ylabel('Customer state')\n"
                "plt.tight_layout()\n"
                "plt.show()"
            ),
            md("## 7. Payment Analysis\n"
               "Question: Which payment methods account for transaction records, distinct orders, and recorded payment value?\n\n"
               "`order_payments` is at payment-record granularity: an order may have multiple records. Therefore transaction count and distinct order count are both reported."),
            code(
                "payment_summary = payments.groupby('payment_type').agg(\n"
                "    payment_records=('payment_type', 'size'),\n"
                "    distinct_orders=('order_id', 'nunique'),\n"
                "    total_payment_value=('payment_value', 'sum'),\n"
                "    average_payment_record=('payment_value', 'mean')\n"
                ").sort_values('total_payment_value', ascending=False)\n"
                "payment_summary"
            ),
            code(
                "fig, axes = plt.subplots(1, 2, figsize=(14, 5))\n"
                "sns.barplot(data=payment_summary.reset_index(), x='payment_type', y='distinct_orders', ax=axes[0], color='#6B5B95')\n"
                "axes[0].set(title='Distinct Orders by Payment Type', xlabel='Payment type', ylabel='Distinct orders')\n"
                "sns.barplot(data=payment_summary.reset_index(), x='payment_type', y='total_payment_value', ax=axes[1], color='#C06C3E')\n"
                "axes[1].set(title='Recorded Payment Value by Type', xlabel='Payment type', ylabel='BRL')\n"
                "for ax in axes: ax.tick_params(axis='x', rotation=30)\n"
                "plt.tight_layout()\n"
                "plt.show()\n\n"
                "payments['payment_installments'].describe()[['count', 'mean', '50%', 'max']]"
            ),
            md("## 8. Delivery Analysis\n"
               "Question: How long does delivery take for orders with both a purchase timestamp and a customer-delivery timestamp?\n\n"
               "Missing delivery dates are excluded only from this delivery-time calculation. They are not filled or removed from the processed data."),
            code(
                "delivery = orders.dropna(subset=['order_purchase_timestamp', 'order_delivered_customer_date']).copy()\n"
                "delivery['delivery_days'] = (delivery['order_delivered_customer_date'] - delivery['order_purchase_timestamp']).dt.total_seconds() / 86400\n"
                "delivery_stats = delivery['delivery_days'].agg(['count', 'mean', 'median', 'min', 'max'])\n"
                "delivery_stats.to_frame('Delivery days')"
            ),
            code(
                "plt.figure(figsize=(10, 5))\n"
                "sns.histplot(data=delivery, x='delivery_days', bins=50, color='#0F6B78')\n"
                "plt.xlim(0, delivery['delivery_days'].quantile(0.99))\n"
                "plt.title('Delivery Time Distribution (up to 99th Percentile)')\n"
                "plt.xlabel('Days from purchase to customer delivery')\n"
                "plt.ylabel('Orders')\n"
                "plt.tight_layout()\n"
                "plt.show()"
            ),
            md("Limit: the plot intentionally limits the x-axis to the 99th percentile to make the main distribution readable; the statistics still use all analysable deliveries."),
            md("## 9. Customer Satisfaction\n"
               "Question: How are review scores distributed, and is delivery time associated with customer satisfaction?\n\n"
               "Reviews are first aggregated to one mean score per order because an order can have more than one review record. This avoids duplicating delivery observations."),
            code(
                "review_by_order = reviews.groupby('order_id', as_index=False).agg(review_score=('review_score', 'mean'))\n"
                "satisfaction = delivery.merge(review_by_order, on='order_id', how='inner')\n"
                "review_stats = reviews['review_score'].agg(['count', 'mean', 'median'])\n"
                "relationship = satisfaction[['delivery_days', 'review_score']].corr().iloc[0, 1]\n"
                "review_stats.to_frame('Review score'), relationship"
            ),
            code(
                "fig, axes = plt.subplots(1, 2, figsize=(14, 5))\n"
                "sns.countplot(data=reviews, x='review_score', ax=axes[0], color='#6B5B95')\n"
                "axes[0].set(title='Review Score Distribution', xlabel='Review score', ylabel='Review records')\n"
                "sns.boxplot(data=satisfaction, x='review_score', y='delivery_days', ax=axes[1], color='#80B1D3', showfliers=False)\n"
                "axes[1].set(title='Delivery Time by Review Score', xlabel='Mean review score per order', ylabel='Delivery days')\n"
                "plt.tight_layout()\n"
                "plt.show()"
            ),
            md("Interpretation: the observed correlation describes association, not causality. Review scores can also be affected by product quality, expectations, customer service, or other unobserved factors."),
            md("## 10. Seller Analysis\n"
               "Question: Which sellers contribute the largest observed item volume, order reach, and product revenue?\n\n"
               "This is an activity summary, not a complete performance ranking: it does not include margin, stock, returns, advertising, or seller service quality."),
            code(
                "seller_summary = item_fact.groupby('seller_id').agg(\n"
                "    items_sold=('order_item_id', 'size'),\n"
                "    distinct_orders=('order_id', 'nunique'),\n"
                "    product_revenue=('price', 'sum')\n"
                ").sort_values('product_revenue', ascending=False)\n"
                "seller_summary.head(10)"
            ),
            code(
                "top_sellers = seller_summary.head(10).sort_values('product_revenue')\n"
                "plt.figure(figsize=(11, 6))\n"
                "sns.barplot(data=top_sellers.reset_index(), x='product_revenue', y='seller_id', color='#49796B')\n"
                "plt.title('Top 10 Sellers by Product Revenue')\n"
                "plt.xlabel('Product revenue (BRL)')\n"
                "plt.ylabel('Seller ID')\n"
                "plt.tight_layout()\n"
                "plt.show()"
            ),
            md("## 11. Relationships Between Variables\n"
               "Question: How do category prices vary, and how does order volume relate to category revenue?\n\n"
               "The charts use the top revenue categories so that comparisons remain readable."),
            code(
                "top_categories = category_summary.head(10).index\n"
                "price_categories = item_fact[item_fact['category_display'].isin(top_categories)]\n"
                "fig, axes = plt.subplots(1, 2, figsize=(16, 6))\n"
                "sns.boxplot(data=price_categories, x='price', y='category_display', ax=axes[0], showfliers=False, color='#80B1D3')\n"
                "axes[0].set(title='Item Price by Top Revenue Category', xlabel='Item price (BRL)', ylabel='Category')\n"
                "sns.scatterplot(data=category_summary.reset_index(), x='items_sold', y='product_revenue', ax=axes[1], color='#C06C3E')\n"
                "axes[1].set(title='Category Volume and Product Revenue', xlabel='Items sold', ylabel='Product revenue (BRL)')\n"
                "plt.tight_layout()\n"
                "plt.show()"
            ),
            md("Freight versus geographical distance is not analysed here. The available postal-code/geolocation data would require a defensible customer-to-seller location matching method; using raw coordinates without that method could mislead."),
            md("## 12. Initial Business Insights"),
            md(
                "### 1. Observation\n"
                "The observed data contains 99,441 orders, 96,096 unique customers, 112,650 items, 32,951 products, and 3,095 sellers.\n\n"
                "### Evidence\n"
                "Product revenue is BRL 13.59M and observed freight is BRL 2.25M.\n\n"
                "### Business Meaning\n"
                "The marketplace has a broad catalogue and multi-seller structure.\n\n"
                "### Limitation\n"
                "Product revenue is not a profitability measure and excludes other commercial adjustments.\n\n"
                "### 2. Observation\n"
                "November 2017 is the highest observed product-revenue month, at about BRL 1.01M across 7,451 orders.\n\n"
                "### Evidence\n"
                "It is the maximum of the monthly product-revenue series.\n\n"
                "### Business Meaning\n"
                "It is a period worth investigating in later business analysis.\n\n"
                "### Limitation\n"
                "The data window is too short, and edge months are incomplete, to confirm seasonality.\n\n"
                "### 3. Observation\n"
                "`bed_bath_table` has the greatest item volume (11,115), while `health_beauty` has the highest product revenue (about BRL 1.26M).\n\n"
                "### Evidence\n"
                "The categories differ in average item price: about BRL 93 versus BRL 130.\n\n"
                "### Business Meaning\n"
                "High volume and high revenue are different commercial lenses.\n\n"
                "### Limitation\n"
                "This does not measure margin or product availability.\n\n"
                "### 4. Observation\n"
                "Sao Paulo (SP) is the largest customer state in the observed data, with 41,375 orders and about BRL 5.20M in product revenue.\n\n"
                "### Evidence\n"
                "SP leads the state-level order and revenue summaries.\n\n"
                "### Business Meaning\n"
                "Commercial activity is geographically concentrated in the observed customers.\n\n"
                "### Limitation\n"
                "Customer state is not a measurement of total addressable market.\n\n"
                "### 5. Observation\n"
                "Credit card is the largest recorded payment type, with 76,505 distinct orders and BRL 12.54M in payment value.\n\n"
                "### Evidence\n"
                "It exceeds the other payment types in both measures.\n\n"
                "### Business Meaning\n"
                "Payment mix is concentrated in one recorded payment method.\n\n"
                "### Limitation\n"
                "Payment rows are not identical to order rows because an order may have multiple payment records.\n\n"
                "### 6. Observation\n"
                "Among 96,476 orders with usable delivery dates, mean delivery time is 12.56 days and median delivery time is 10.22 days.\n\n"
                "### Evidence\n"
                "The mean exceeds the median, indicating a right-tailed delivery-time distribution.\n\n"
                "### Business Meaning\n"
                "A small set of long deliveries affects the average customer experience measure.\n\n"
                "### Limitation\n"
                "Orders without a delivery timestamp are excluded from this calculation.\n\n"
                "### 7. Observation\n"
                "Delivery time and average review score per order have a negative correlation of about -0.33.\n\n"
                "### Evidence\n"
                "Orders with score 1 average 21.34 delivery days, compared with 10.68 days for score 5.\n\n"
                "### Business Meaning\n"
                "Delivery experience is plausibly an important customer-satisfaction dimension to investigate.\n\n"
                "### Limitation\n"
                "This association does not establish that delivery time caused a review score.\n\n"
                "### 8. Observation\n"
                "The top seller by observed product revenue generated about BRL 229k, but another seller has the largest item volume among the top revenue group.\n\n"
                "### Evidence\n"
                "Seller rankings differ when sorted by item count versus revenue.\n\n"
                "### Business Meaning\n"
                "Seller activity should be assessed through more than one measure.\n\n"
                "### Limitation\n"
                "Revenue alone is not seller performance or profitability."
            ),
            md("## 13. EDA Conclusion\n"
               "This EDA establishes a business baseline using processed data: activity is concentrated by state, category, payment type, and seller; category volume differs from revenue; and longer delivery times are associated with lower review scores. These are evidence-backed observations for later modelling and BI work, not causal findings or recommendations."),
        ]
    )


def main() -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8") as file:
        nbf.write(build_notebook(), file)
    print(f"Wrote {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
