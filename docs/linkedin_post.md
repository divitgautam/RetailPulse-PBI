# LinkedIn post: RetailPulse-PBI

**Attach, in this order:**
1. `docs/key_insights.png` (portrait, shows best in the feed)
2. `docs/approach_diagram.png`
3. `docs/dashboard/01_customer_retention.png`
4. `docs/dashboard/02_category_profitability.png`
5. `docs/dashboard/03_kpi_profit_per_customer.png`
6. `docs/dashboard/05_forecast_levers.png`

Replace `<GitHub link>` before posting. About 2,300 characters, under LinkedIn's 3,000 limit.

---

## Post text (copy from here)

I was given three questions about an online retail business. The data answered a fourth one nobody asked.

The brief:
1. How many customers buy once vs come back?
2. Which product categories actually make money?
3. Design a KPI that ties customer behaviour to profit.

Before building a single chart, I audited the data. 20 checks, 4 failures:
- duplicate customer IDs (one ID was shared by three different names)
- a many-to-many relationship that would have quietly double-counted
- order totals repeated on every line: summing them overstates revenue 4.6x
- cancelled orders with no date

Fixing those first is the reason every number in the Power BI report matches my Python analysis to the rupee.

What the data said:

🔁 Retention carries the business. 53% of buyers came back, and they generate 76% of gross profit, about 2.8x more per customer than one-time buyers.

⏳ But they come back slowly. The median gap to a second order is 254 days, and 54% return within two years. A customer quiet for a year is not lost. I tested this: "silent for 2x their usual gap" did not predict anything.

📉 The real problem was upstream. New sign-ups stopped in September 2024. New buyers fell from 128 to 64 to 28, while like-for-like profit actually rose 6% in 2025. The base is healthy; the funnel is empty.

💸 Discounts cost margin and buy no loyalty. Margin drops from 30% to 17% as item discounts go from 0% to 15%. All 29 loss-making order lines stacked two discounts. And a discounted first order did not make customers more likely to return.

🏷️ Beauty leads profit (27%), Home & Kitchen trails. Electronics has the thinnest margin.

The KPI I proposed: Profit per Active Customer = orders per customer x average order value x margin. One number that moves only when customers buy more often, spend more, or you protect margin.

Then I forecast 2026 with a customer-level simulation (2,000 runs, backtested on held-out months): about ₹1 crore of gross profit, with a 20 to 24% chance of hitting the KPI target if nothing changes.

The levers, sized:
→ Cap item discounts at 10%, no stacking: +₹12 L, at zero cost
→ Convert 20% of the 80 customers who signed up but never ordered: +₹16 L
→ Lift repeat rate from 53% to 60%: +₹12 L (and a lesson: this lowers profit per customer, so never read that KPI alone)

My biggest takeaway: the most valuable step was the boring one. Auditing the data first changed the answers.

Built with Power BI (DAX, Power Query, 5 report pages), Python (pandas, statsmodels, scipy, scikit-learn) and a lot of reconciliation.

Full project (RetailPulse-PBI), notebooks and report: <GitHub link>

What would you have checked first?

#PowerBI #DataAnalytics #DAX #Python #CustomerAnalytics #Forecasting #BusinessIntelligence #DataQuality

---

## Shorter alternative (about 900 characters)

Three questions about an online store, one surprise answer.

Recurring customers are 53% of buyers but 76% of profit. They return slowly (median 254 days), so a quiet customer is not a lost one.

Growth did not stall because customers left. New sign-ups stopped in Sep 2024, while like-for-like profit rose 6%.

Discounts cut margin from 30% to 17% and did not bring anyone back.

I audited the data before charting it (20 checks, 4 fixes, including a 4.6x revenue overcount), built 5 Power BI pages and a backtested 2026 forecast: about ₹1 Cr gross profit.

Cheapest lever: cap discounts at 10%, no stacking, worth +₹12 L.

Project (RetailPulse-PBI): <GitHub link>

#PowerBI #DataAnalytics #Python #Forecasting
