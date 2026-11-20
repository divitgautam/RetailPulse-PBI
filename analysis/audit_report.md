# Data Audit Report: Online Sales Data

**Source:** `Online Sales Data.xlsx` (Customers 307 rows, Products 200, Order_Items 1,500 lines / 405 orders, 9 Jan 2023 to 31 Oct 2025)
**Run:** 20 Nov 2026, `analysis/01_audit.ipynb` (20 checks: 4 FAIL, 7 WARN, 9 PASS)
**Evidence:** `output/audit_findings.csv`, `output/audit_exceptions.xlsx` (offending rows per check), `output/figures/`

Cleaned Python totals reconcile exactly with the Power BI report: net sales ₹10,82,22,683, gross profit ₹2,86,43,394, 386 revenue orders, 220 buying customers, 300 customers.

---

## Verdict

The **sales and profit numbers are trustworthy**. Keys link, order totals add up line by line, prices and costs are valid, and no product sells at list price below cost.

Four fields **cannot be used as they are**: SKU prefix, tax rate, customer `join_date`, and `stock_quantity`. The `segment` label also does not reflect behaviour. Several of these look like synthetic-data artefacts, so confirm with the data owner before drawing conclusions from them.

---

## FAIL: wrong data that affects analysis

| # | Finding | Impact | Recommended fix |
|---|---|---|---|
| Q1 | **Duplicate customer IDs.** CUST0001 has 4 rows (the extra copies are partial subsets of the full row, so nothing is lost). CUST0300 has 3 rows with *different first names* (Rhea, Roni, Ritesh), which may be different people sharing one ID. There is also 1 row with a blank ID. | Inflated customer counts; a many-to-many join in Power BI (already fixed by dedupe) | Keep the dedupe. Ask the source system owner whether Roni and Ritesh are real customers who need their own IDs. |
| Q10 | **SKU prefixes are meaningless.** 165 of 200 SKUs have a prefix that does not match the category (for example `BE-` on Fashion). The SKU *number* always matches `product_id`. | Any grouping by SKU prefix is wrong | Never derive category from SKU. Use `Products.category`. |
| Q11 | **Tax rate does not follow the product.** All 25 subcategories carry more than one rate (0/5/12/18%). The same product type is taxed at 0% in one order and 18% in another. | `line_total` (tax-inclusive) is unreliable for comparisons; under GST the rate should be fixed per HSN code | Analyse on **net sales excluding tax** (already done). Raise with finance if the tax data is meant to be real. |
| Q12 | **Orders before joining.** 73 orders (18%) from 55 customers are dated before the customer's `join_date`: a median of 179 days earlier and up to 588 days. 18% of customers' first order precedes their join date. | Join-to-first-order lag, acquisition and cohort analysis built on `join_date` will be wrong | Define acquisition by **first order date**, not `join_date`. Treat `join_date` as unreliable until it is explained. |

## WARN: handled, or worth knowing

| # | Finding | Handling |
|---|---|---|
| Q2 | **23 order lines have no `order_date`.** All are *Cancelled*, across 13 orders, and each order has its date on another line. | **Fixed.** Filled from the order in Python (`lines.order_date_imputed`) and in the Power BI `Order_Items` query (20 Nov 2026). |
| Q2 | **Stub customer CUST0301 "Rakesh":** only an ID and first name, no orders. One clean customer is missing most fields. | **Fixed.** Dropped in Power BI and Python (no email, join date or segment). Registered customers are now 300 and never-ordered 80. |
| Q15 | **`stock_quantity` is unrelated to sales.** Stock is 0–997 per product against about 10 units sold in 34 months, which is a median cover of 158 years. | Not usable for inventory or demand planning. Question 41 (category demand vs stock) is blocked until real stock data exists. |
| Q16 | **29 revenue lines were sold below cost** (−₹1.07 L). *Every one* stacks an item discount and an order discount, and 17 use the 15% item discount. | Business issue, not a data error: a discount guardrail is needed. |
| Q17 | **19 orders (4.7%) were cancelled or returned.** Credit card is highest at 6.4%. | The counts are too small for strong conclusions. Revisit with more data. |
| Q18 | **The segment label does not match behaviour.** Wholesale orders average 4.8 units vs 5.1 for Retail. | Do not treat "Wholesale" as bulk buyers. Segment-based insights carry little signal. |
| Q13 | All emails are `@example.com` and all phones are valid-format. | **The dataset looks synthetic or anonymised.** Patterns such as tax randomness and stock levels may be generator artefacts rather than business reality. |

## PASS

Unique keys (order items, products, SKUs, emails) · no orphan customers or products · order headers consistent across lines · `items_total` = Σ `line_total` for all 405 orders and `line_total` matches its formula on every line · implied shipping always one of 10 tiers (₹0–300, no link to order value) · order prices equal list prices (no price history) · cost < price for every product (list margin 15–54%) · each city maps to one state, all in India.

---

## What this changes for the next steps

1. **EDA and forecasting:** use first order date for acquisition and cohorts. Use net sales excluding tax. Keep monthly grain.
2. **Do not plan with:** SKU prefixes, tax rates, `join_date`, `stock_quantity`, or `segment` as a proxy for bulk buying.
3. **Power BI follow-ups: done 20 Nov 2026.** The undated cancelled lines are filled from their order, and stub customer CUST0301 is removed. Sales, profit and order totals are unchanged.
4. **Questions for the data owner:**
   - Is the data synthetic?
   - What does `join_date` represent?
   - Are Roni and Ritesh real customers?
   - Is the tax rate meant to vary by order?

## Reproduce

```powershell
cd D:\Wolf\PBI\RetailPulse-PBI\analysis
python _make_notebooks.py
jupyter nbconvert --to notebook --execute --inplace 00_load_clean.ipynb 01_audit.ipynb
```

`00_load_clean` writes `data/*.parquet` and asserts that the totals match Power BI. Later notebooks should load from those files.
