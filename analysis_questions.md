# Inxite-Out: Analysis Question Bank

Next-step questions for working in VS Code (Python / notebooks) on `Online Sales Data.xlsx`.
Sheets: **Customers** (300 after dedupe and stub removal), **Products** (200), **Order_Items** (1,500 lines, 405 orders, Jan 2023 to Oct 2025).

Each question lists the columns involved and a suggested method. Do them in order: **Audit, then EDA, then Forecasting**. The forecasts are only as good as the audit.

---

## Data facts to carry into Python

- `items_total` and `total_amount` are **order-level** values repeated on every line. Aggregate them per `order_id` with `first()`, never `sum()`.
- `total_amount = items_total x (1 - discount_percent/100) + shipping`. Shipping is implied, not a column.
- `line_total = unit_price x quantity x (1 - item_discount_percent/100) x (1 + tax_percent/100)`. It includes tax.
- Net sales (ex tax) = `unit_price x quantity x (1 - item_disc) x (1 - order_disc)`. Gross profit = net sales - `cost_price x quantity`.
- Treat `Cancelled` and `Returned` as non-revenue.
- The data is small: about 12 orders a month. Prefer monthly or quarterly grain, simple models and wide intervals.

---

## 1. Data audit

### Completeness and uniqueness
1. How many `customer_id` values are duplicated in the raw Customers sheet, and which fields differ between the copies? Is "keep the most complete row" the right rule, or should rows be merged field by field? *(groupby + nunique per column)*
2. Which customer fields are null, and how often? Are nulls random or clustered (by join date, state, segment)? *(missingness matrix, `missingno`)*
3. Are `order_item_id` and `product_id` unique in their own tables? Is `sku` unique?
4. Does every `Order_Items.customer_id` exist in Customers, and every `product_id` in Products? *(anti-joins)*
5. Are there orders with no lines, or lines whose `order_id` maps to more than one `order_date`, `customer_id`, `status`, `payment_method` or `discount_percent`? *(groupby order_id, nunique > 1)*

### Consistency and validity
6. Does `items_total` equal the sum of `line_total` for every order? Report the difference distribution. *(currently 405/405 match; re-check on new data)*
7. Is the implied shipping (`total_amount - items_total x (1 - disc)`) always one of the known tiers (0, 30, 50, 60, 70, 100, 140, 150, 200, 300)? What drives the tier: order value, state, or payment method?
8. Does `Order_Items.unit_price` always equal `Products.unit_price`? If prices change over time, which is the source of truth?
9. Is `cost_price < unit_price` for every product? What is the margin distribution by category?
10. Do SKU prefixes (`BE-`, `EL-`, `SP-`...) map to anything? They do not match `category`. Is this a labelling error in the source system?
11. Are discount (0/5/10/15) and tax (0/5/12/18) values only from allowed sets? Does tax rate follow category or subcategory, as Indian GST would?
12. Are dates valid? Check `order_date` against `join_date` (orders before joining?) and `birth_date` (customers under 18 or over 100?).
13. Are `phone` values valid 10-digit Indian mobiles? Are `email` values well-formed and unique per customer?
14. Do `city`, `state` and `country` agree (for example, Nagpur sits under Maharashtra)? Any spelling variants?
15. Is `stock_quantity` a snapshot or a running value? Does it reconcile with units sold?

### Business-rule checks
16. Which order lines have negative gross profit (29 today)? Is it always the 15% item discount stacked with an order discount?
17. Do cancelled or returned orders cluster by payment method, category, state, or order value?
18. Are there customers whose `segment` (Retail/Wholesale) contradicts their behaviour (for example, "Wholesale" with tiny order sizes)?

---

## 2. Exploratory data analysis

### Sales and profit over time
19. What is the monthly trend in orders, net sales, gross profit and margin? Is there seasonality (festive Q4, month-end, weekday)? *(resample M; STL decomposition)*
20. 2025 runs to October only. On a like-for-like Jan to Oct basis, is the business growing or shrinking?
21. How does average order value trend, and is any change driven by units per order or price mix?

### Customers and retention
22. Build monthly or quarterly acquisition cohorts. What share of each cohort orders again within 90, 180 and 365 days? *(cohort retention heatmap)*
23. What is the typical gap between a first and second order? After how many days without an order does a customer rarely come back? *(inter-purchase time; Kaplan-Meier)*
24. Why did new-customer acquisition drop from 128 to 64 to 28? Is it fewer sign-ups (`join_date`) or fewer sign-ups converting to a first order?
25. What is the lag between `join_date` and first order? Who are the 80 never-ordered customers (segment, age, state, join date)?
26. RFM segmentation: which customers are champions, at risk, or lost? *(recency from 31 Oct 2025, frequency, monetary = gross profit)*
27. What predicts becoming a recurring customer: first-order category, value, discount, payment method, age group, state or segment? *(logistic regression or a tree on first-order features)*
28. Does a discount on the first order lead to more repeat orders, or only lower margin?

### Products and categories
29. Pareto: what share of profit comes from the top 20% of products and subcategories? Which products never sold?
30. Which categories or subcategories are bought together in the same order? *(market basket: support, lift)*
31. Which categories do recurring customers buy that one-time customers do not?
32. Is margin erosion from discounts uniform across categories, or concentrated in a few?

### Geography, channel and demographics
33. Which states and cities have the highest profit per customer and repeat rate? Is there an untapped region?
34. How do payment methods differ in AOV, cancellation rate and repeat rate? Is Cash on Delivery riskier?
35. How do age group and gender relate to spend, category mix and retention? (Check sample sizes first; some groups are small.)
36. How do Retail and Wholesale differ in order size, frequency, discount use and margin?

---

## 3. Forecasting

Grain: monthly is the practical minimum (about 34 points). Always hold out the last 6 months, compare against a seasonal-naive baseline, and report intervals.

### What to forecast
37. Monthly **net sales** and **gross profit** for Nov 2025 to Dec 2026. *(ETS / SARIMA / Prophet vs seasonal naive; MAPE on holdout)*
38. Monthly **order count** and **active customers**. Model orders as a count series. *(Poisson/negative-binomial regression with trend and month terms; Croston-style if sparse)*
39. **New-customer acquisition** per month. If the decline continues, when does the business rely almost entirely on existing customers?
40. **Profit per Active Customer** (the KPI) for 2026. Forecast its drivers (orders per customer, AOV, margin) separately and multiply them. Is the +5% target reachable?
41. **Category-level demand** (units by category per quarter) for stock planning, compared with `stock_quantity`. *(hierarchical forecast, reconciled bottom-up)*
42. **Cancellation/return rate** next quarter, and expected lost profit.

### Customer-level prediction
43. Probability that each customer orders again in the next 90 days. *(BG/NBD with the `lifetimes` package, or a classifier on RFM features)*
44. Expected 12-month customer lifetime value (gross profit). *(BG/NBD + Gamma-Gamma)* Rank customers for retention campaigns.
45. Churn risk: which currently recurring customers show a lengthening purchase gap?

### Scenarios
46. What happens to 2026 gross profit if item discounts are capped at 10%? *(re-price historical lines; use an assumed volume elasticity)*
47. If 20% of the 80 never-ordered customers convert at the average first-order value, what is the profit uplift?
48. If the repeat rate rises from 53% to 60%, what is the effect on PPAC and total profit?

---

## Suggested project layout in VS Code

```
analysis/
  00_load_clean.ipynb     # load sheets, dedupe customers, build order-level + line-level frames, save parquet
  01_audit.ipynb          # questions 1-18, outputs an audit_report.md
  02_eda.ipynb            # questions 19-36
  03_forecast.ipynb       # questions 37-42
  04_customer_models.ipynb# questions 43-48
  src/metrics.py          # net_sales, gross_profit, is_revenue, same definitions as Power BI
```

Python packages: `pandas`, `openpyxl`, `numpy`, `matplotlib`/`seaborn` or `plotly`, `statsmodels`, `prophet` (optional), `lifetimes`, `scikit-learn`, `mlxtend` (basket analysis), `missingno`.

Reconciliation check: totals in `src/metrics.py` should match Power BI exactly (Net Sales ₹10,82,22,683; Gross Profit ₹2,86,43,394; 386 revenue orders; 220 purchasing customers).
