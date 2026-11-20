# Forecast Report: Nov 2025 – Dec 2026

**Notebook:** `analysis/03_forecast.ipynb` (questions 37–42) · **Run:** 20 Nov 2026
**Outputs:** `output/forecast_monthly.csv` (P10/P50/P90 by month, scenario and metric; ready to load into Power BI),
`output/forecast_category_units_2026.csv`, `output/forecast_backtest.csv`, `output/figures/q37_*.png`

---

## Headline

**2026 gross profit of about ₹1 crore, give or take ₹18 L.** That is flat on 2025, whatever happens with sign-ups, but only if existing customers keep buying at today's rate.

| 2026 | A · No new sign-ups | B · Sign-ups resume (~7/mo) | C · Activation push (2× conversion) |
|---|---|---|---|
| Gross profit, median | **₹96.9 L** | ₹107.8 L | ₹111.0 L |
| Gross profit, 80% range (A) | ₹79.9 L – ₹115.4 L | | |
| Net sales, median (A) | ₹358.8 L | | |
| Revenue orders, median | 132 | 148 | 152 |
| New buyers (Nov 25 – Dec 26) | 27 | 41 | 43 |
| Probability PPAC ≥ target | 24% | 20% | 22% |

Reference points:
- 2025 Jan–Oct actual gross profit was ₹83.6 L, which annualises to about ₹100 L.
- The long-run average cross-check is ₹101 L.

---

## How the forecast works

The business now runs on repeat orders (75% of orders in 2025), so the main model simulates customers rather than extending a line:

| Input (from the last 12 months) | Value | Meaning |
|---|---|---|
| Repeat hazard *h* | ~4% per buyer per month | Each of the 220 buyers places an order in a given month with this probability. It has been stable for 24 months. |
| Pool conversion *c* | ~2.8% per month | Each registered customer who has never ordered converts with this probability (80 left). |
| Cancel/return *q* | ~4.9% | Share of orders that never become revenue. |
| Order value and profit | Resampled from real orders | Keeps the true spread of order sizes and category mix. |

2,000 simulations give the medians and 80% ranges. Parameter uncertainty is included: *h*, *c* and *q* are drawn from their posterior distributions in each run.

## Backtest (train to Apr 2025, forecast May–Oct 2025)

| Model | Orders, 6-mo total error | Profit, 6-mo total error | Profit MAE / month |
|---|---|---|---|
| **Customer-base simulation** | **−1%** | −10% | ₹2.1 L |
| Exponential smoothing (= long-run average) | −2% | **−2%** | **₹1.6 L** |
| Trailing 12-month mean | −3% | −11% | ₹2.2 L |
| Theta | −5% | −12% | ₹2.2 L |
| Seasonal naive | +6% | −8% | ₹3.4 L |

- The simulation's 80% range contained the actual 6-month totals for both orders and profit.
- It predicts **order volume** best. On **profit** it ran about 10% low: recent orders earned more per order (2025 margin recovered to 26.8%) than its history window. **Treat the scenario-A profit median as slightly conservative.**
- Single months are unpredictable for every method: monthly profit varies about 41% around its mean. **Plan on quarterly or annual totals, not months.**
- No method found usable seasonality, so none is assumed.

---

## Answers by question

**Q37 · Sales and profit.**
- 2026 gross profit is ₹96.9 L (scenario A) to ₹107.8 L (B). Net sales are about ₹3.6 Cr (A).
- The long-run-average cross-check gives ₹101 L.
- Plan around ₹1 crore of gross profit, with a downside case near ₹80 L.

**Q38 · Orders and active customers.**
- 132 revenue orders in scenario A (2025 annualised is about 137), roughly 11 ordering customers a month.
- Volume holds even with zero acquisition, because 220 buyers × 4% a month keeps replenishing orders.

**Q39 · Acquisition.**
- With no sign-ups, only about 27 new buyers arrive (the remaining pool drains from 80 to about 53), and 84% of 2026 orders are repeat orders.
- Restarting sign-ups at the 2024 pace adds about 14 buyers and **about ₹11 L** of 2026 profit.
- Doubling conversion of the existing pool (scenario C) adds about ₹14 L, more than restarting sign-ups, at no acquisition cost. **Activating the 80 is the cheapest growth lever.**
- The real value of sign-ups is long-term: each new buyer adds about 4% a month of future repeat orders.

**Q40 · KPI: Profit per Active Customer.**
- Expected 2025 full-year PPAC is about ₹99,350, so the 2026 target (+5%) is about ₹1,04,300.
- Forecast 2026 PPAC is about ₹92,200 (80% range ₹74,500–₹1,13,800). **The chance of hitting the target is only 20–24%.**
- Acquisition barely changes PPAC because it is a ratio: new buyers add profit and customers in proportion.
- To move it you need the drivers: **more orders per customer** (follow-ups at 3, 6 and 12 months), **higher order value** (designed bundles), and **margin** (a discount cap; see the EDA).

**Q41 · Category demand 2026** (units, scenario A median):

| Beauty | Sports | Electronics | Fashion | Home & Kitchen | Total |
|---|---|---|---|---|---|
| 159 | 144 | 129 | 114 | 113 | ~660 (≈165 a quarter) |

Quarterly splits are in the notebook. Checking these against stock is **not possible**: `stock_quantity` is a static snapshot unrelated to sales (audit Q15).

**Q42 · Cancellations.**
- Rate about 4.9%. For 2026 Q1, expect a median of 1 lost order (0–3), about ₹0.7 L of profit.
- There are too few events to model what drives them. Monitor the monthly rate against about 5%.

---

## Caveats

1. **The biggest unknown is whether sign-ups really stopped** on 25 Sep 2024 or the extract is cut off. Scenarios A and B bracket this, so confirm with the data owner.
2. **The model assumes the 4% monthly hazard holds.** If repeat buying slows, scenario A falls with it, as it would in any model.
3. The data looks synthetic (audit): use the method for planning, but re-run on production data before committing targets.

## Re-run

```powershell
cd D:\Wolf\PBI\RetailPulse-PBI\analysis
python _make_forecast_notebook.py
jupyter nbconvert --to notebook --execute --inplace 03_forecast.ipynb
```

## Next step

`04_customer_models` (questions 43–48):
- Per-customer probability of ordering in the next 90 days.
- 12-month customer lifetime value.
- Churn-risk list.
- Discount-cap, activation and repeat-rate "what-if" scenarios, built on this simulation.
