# Customer Models and Scenarios Report

**Notebook:** `analysis/04_customer_models.ipynb` (questions 43–48) · **Run:** 20 Nov 2026
**Outputs:** `output/customer_scores.csv` (every buyer: P(alive), P(order in 90 days), expected orders, 12-month CLV, RFM segment, churn flag),
`output/churn_risk_customers.csv`, `output/scenario_discount_cap.csv`, `output/customer_model_findings.csv`, `output/figures/q43_*`, `q44_*`

---

## The key finding: every buyer behaves the same

The standard customer-value model (BG/NBD, which predicts each person's future orders) was fitted and tested on held-out months. It **collapsed to a single buying rate shared by every buyer: about 3.6% a month, with no drop-out.** That is a valid result, not a failed fit:

- **Dispersion test:** repeat orders per buyer match one shared Poisson rate (dispersion 1.03, where 1.0 means identical buyers; p=0.37).
- **No ranking power:** the model ranks who will buy next no better than chance (AUC 0.45). Recency alone scores 0.47 and frequency alone 0.43.
- **Silence means nothing:** buyers who had been silent for twice their usual gap were *not* less likely to buy in the next 6 months (11% vs 18%, p=0.53).

**What this means for the business:**
1. **Don't build propensity scoring or churn prediction on this data.** There is nothing to separate customers. A buyer silent for a year is as likely to order next month as one who just ordered.
2. **The RFM segments from the EDA describe the past only.** "Champions" and "At risk" are not predictive labels.
3. **Treat every buyer the same:** one follow-up cadence for everyone (for example at 3, 6 and 12 months), not targeted lists.
4. **Plan on totals, which are reliable.** The customer-base simulation in `03` forecast aggregate orders within 1%.
5. The audit already suggested the data may be **synthetic**, and memoryless, identical buyers are typical of generated data. **Re-run this notebook on production data:** real customers usually *do* differ, and then these scores become useful.

---

## Answers by question

**Q43 · Probability of ordering in the next 90 days.**
- Every buyer is at **about 10%** (range 10–11%), and P(alive) is about 100% for everyone.
- Expected orders from the 216 buyers in the next 90 days: **about 23**.
- In the backtest (calibrated to Apr 2025), BG/NBD under-forecast May–Oct repeat orders by 20% (38 vs 47). The simulation in `03` did better.

**Q44 · 12-month customer lifetime value (gross profit).**
- Existing buyers are expected to generate **about ₹69.7 L** over 12 months. That cross-checks with 216 buyers × 3.6% a month × 12 months × average profit per order.
- Per buyer it is almost flat: median ₹31,900, highest ₹37,600. **The top 20% of buyers hold only 21% of future value.**
- Order value doesn't depend on order frequency (correlation 0.09), so the order-value model behind this is valid.

**Q45 · Churn risk.**
- 38 repeat buyers are silent for twice their own usual gap, a historical run-rate of about ₹41 L a year.
- The rule **does not predict** churn (see above).
- `churn_risk_customers.csv` is still a sensible **re-engagement contact list**, but not a risk ranking.

**Q46 · Cap item discounts at 10% and stop stacking.**

| Rule (last 12 months re-priced) | Volume holds | Affected orders −10% | Break-even volume loss |
|---|---|---|---|
| **Item cap 10%, no stacking** | **+₹12.2 L (+12.8%)** | +9.2% | 36% |

The cap only stops paying off if more than a third of the affected volume disappears. The EDA found discounts don't drive repeat buying, so this is **the strongest single profit lever identified**. Other variants (cap only; 5% cap) are in `scenario_discount_cap.csv`.

**Q47 · 20% of the 80 never-ordered customers convert.**
- 16 new buyers bring about ₹10.8 L from first orders (about ₹67,800 each), plus about ₹5.2 L from repeat orders within a year.
- That is **about ₹16 L, roughly 17% of the 2026 base forecast**, with no acquisition cost.

**Q48 · Repeat rate from 53% to 60%.**
- 16 more of today's one-time buyers ordering again adds **about ₹11.7 L** of profit.
- But **profit per active customer (PPAC) falls**, from ₹92,247 to about ₹89,700: each reactivated buyer adds one average order but also a whole extra "active customer".
- **PPAC rewards deepening relationships and penalises widening them.** Report it alongside total gross profit and repeat rate, so a successful reactivation campaign doesn't look like a KPI miss.

---

## Lever ranking for 2026 (gross profit uplift, about ₹97 L base)

| Lever | Uplift | Confidence | Cost |
|---|---|---|---|
| Discount cap (10%, no stacking) | +₹9–12 L | High: a pure re-pricing calculation | None |
| Activate 20% of the never-ordered | +₹16 L | Medium: depends on the offer working | Low |
| Repeat rate 53% → 60% | +₹12 L | Medium | Low–medium (follow-up programme) |
| Restart sign-ups (2024 pace) | +₹11 L (from `03`) | Depends on the cause of the stop | Marketing spend |

These levers stack, and most of their effect is additive.

## Re-run

```powershell
cd D:\Wolf\PBI\RetailPulse-PBI\analysis
python _make_customer_notebook.py
jupyter nbconvert --to notebook --execute --inplace 04_customer_models.ipynb
```
