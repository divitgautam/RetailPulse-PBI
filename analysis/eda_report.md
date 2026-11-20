# EDA Report: Online Sales Data

**Notebook:** `analysis/02_eda.ipynb` (questions 19–36) · **Data:** 386 revenue orders, 220 buyers, Jan 2023 to Oct 2025
**Evidence:** `output/eda_findings.csv`, `output/rfm_segments.csv`, `output/figures/q19_*` to `q32_*`
**Rules:** acquisition is measured by first order (not `join_date`); money is net sales excluding tax; profit is gross profit.

---

## The story in five points

1. **The business is flat, not collapsing.**
   - Like-for-like (Jan–Oct) gross profit was ₹99.5 L in 2023, ₹79.1 L in 2024 (−21%) and ₹83.6 L in 2025 (+6%).
   - Active customers were 108 → 84 → 90.
   - The 2024 drop was real, but 2025 recovered slightly.

2. **New customers stopped because sign-ups stopped.**
   - The customer master has no sign-ups after **25 Sep 2024** (113 in 2022, 123 in 2023, 64 in 2024, none since).
   - New buyers follow the same curve (128 → 64 → 28), so this is a top-of-funnel problem, not a conversion problem.
   - Repeat orders went from 17% of orders in 2023 to 75% in 2025: the business now runs on existing customers.
   - **First confirm with the data owner** whether registration really stopped or the extract is cut off.

3. **Customers come back slowly but steadily.**
   - The median gap between first and second order is **254 days** (IQR 131–527).
   - The probability of a second order rises almost linearly, about 2.5 points a month, with no plateau: 10% by 90 days, 20% by 180 days, 35% by 1 year, 54% by 2 years.
   - 38% of second orders arrive more than a year after the first.
   - **Don't call a customer "lost" before about 12 months of silence.**

4. **You can't tell from the first order who will come back, and discounts don't help.**
   - No first-order attribute (category, value, discount, payment, segment, gender, age) is significant.
   - A logistic model scores **AUC 0.42**, no better than chance.
   - Repeat rate is 57% when the first order had a discount and 67% without (p=0.75, no real difference).
   - The discount still cuts first-order margin from 33.2% to 26.2%.
   - **Loyalty is earned after the first order, not bought with a discount.**

5. **Discounts are the clearest profit lever.**
   - Margin falls from 0% to 15% item discount in *every* category: Fashion −16.2 pp, Home & Kitchen −8.7 pp (the smallest).
   - Because the erosion is uniform, a single discount cap fits all categories.

---

## Detail by question

| Q | Topic | Finding | So what |
|---|---|---|---|
| 19 | Trend & seasonality | About 11 revenue orders and ₹8.4 L profit a month, very noisy (CV 41%). STL seasonal strength is 0.62 but rests on under 3 yearly cycles. March is strongest and November weakest on average. No weekday effect (p=0.51). | Treat seasonality as **unconfirmed**. Forecasts need wide intervals. |
| 20 | Like-for-like growth | Profit −21% in 2024, +6% in 2025. Orders 123 → 111 → 114. | Stable base. The Power BI line "active customers fell 124 → 90" compares a full year with YTD; like-for-like it is 108 → 84 → 90. |
| 21 | AOV drivers | AOV ₹2.4–3.1 L per quarter. It tracks units per order (r=0.70) about as much as price mix (0.67). Discount rate 7–12%. | Basket size and mix both matter. Bundles target basket size. |
| 22 | Cohorts | 10% reorder within 90 days, 20% within 180, 34% within 365. Cohorts shrank from about 32 buyers a quarter in 2023 to about 7. | Retention is consistent across cohorts. The problem is cohort *size*. |
| 23 | Time to 2nd order | See point 3. | Set the follow-up cadence at 3, 6 and 12 months. Define churn at 12+ months. |
| 24 | Acquisition | See point 2. 80 registered customers are still unconverted. | Fix sign-ups first. Run a first-order offer for the 80. |
| 25 | Never-ordered | Same age (44 vs 43, p=0.57) and segment mix (p=0.56) as buyers. Concentrated in Maharashtra (18), Gujarat (11) and Karnataka (8). | Not a "wrong audience" problem. A simple activation nudge should work. |
| 26 | RFM | **Champions** 33 (31% of profit). **Loyal, growing** 45. **At risk** 35 (25 of them high value), together holding 21% of profit. **New/recent one-off** 30. **Lapsed one-timers** 73. | Win-back list for the 35 at-risk is in `rfm_segments.csv`. **Update (04):** every buyer turns out to share the same buying rate, so RFM describes the past but does not predict who buys next. Use it as a contact list only. |
| 27 | Repeat predictors | See point 4. | Don't segment acquisition spend by first-order traits. |
| 28 | First-order discount | See point 4. | Stop discounting first orders by default. |
| 29 | Pareto | Top 20% of products earn 49% of profit, and 46% of products make 80%. Only 1 product is net loss-making. Serum is the top subcategory (₹22.3 L), Dumbbell Set the lowest (₹4.9 L). | Profit is broad-based. No range cut needed, and no hero-SKU risk. |
| 30 | Basket | 84% of orders span 2+ categories (average 2.6). Pair lift is 0.92–1.05, meaning categories are bought independently. | No natural cross-sell pairs. Bundles must be designed, not discovered. |
| 31 | Mix by customer type | Recurring customers buy slightly more Beauty (+5.5 pp) and less Fashion (−3.1 pp). | Same mix, more often. |
| 32 | Discount erosion | See point 5. | One discount cap (for example max 10%, never stacked). |
| 33 | Geography | Maharashtra 22%, Gujarat 18% and Karnataka 9% of profit. Profit per customer ranges from ₹1.0 L (Tamil Nadu) to ₹1.8 L (West Bengal). Repeat rate doesn't differ by state (p=0.43). | Volume is concentrated, behaviour is not. Regional targeting has little edge. |
| 34 | Payment | Cancel/return 0–6.4% by method (p=0.57). Cash on Delivery: 16 orders, none cancelled. | No payment-method risk to manage. |
| 35 | Demographics | Profit per customer ₹1.1–2.0 L by age group (p=0.11). Repeat rate by gender 48–57%. Small groups. | No reliable demographic lever. |
| 36 | Retail vs Wholesale | Same repeat rate (54% vs 49%) and profit per customer (₹1.3 L each, p=0.93). | The segment label carries no signal (matches audit Q18). |

---

## Implications for forecasting (`03_forecast`)

- **Model the customer base, not just a time series.** With repeat orders at 75% of volume, forecast as active base × orders per customer × AOV × margin, with explicit acquisition scenarios: sign-ups stay at zero, resume at the 2024 rate, or the 80 convert.
- **Keep time-series models simple:** seasonal naive, ETS, and Poisson regression on monthly orders. 34 noisy months cannot support complex models or confirm seasonality.
- **Use the survival curve** (constant hazard of about 2.5% a month) to project second orders from recent one-time buyers, and BG/NBD-style models for customer-level forecasts.
- **Discount-cap scenario:** re-price historical lines at max 10% with no stacking to size the margin gain. Retention is unaffected per Q28.

## Follow-ups

- **Data owner:** did registration stop on 25 Sep 2024, or is the extract cut off? This changes the acquisition forecast completely.
- **Power BI insights page:** reword finding 1 to the like-for-like figures (108 → 84 → 90 active customers; 2025 profit +6%), and make the acquisition point about sign-ups stopping.
