"""Builds the RetailPulse-PBI report pages (PBIR JSON) in the InXiteOut palette, using the shared kit (_build/pbir_kit.py).
Run: python _build/build_report.py   (with Desktop closed, or then "Apply external changes" in Power BI Desktop)

v2 (Nov 2026, after the dashboard scorecard review): action titles from DAX title measures that follow the slicers,
Indian units (₹ L / ₹ Cr) everywhere, change lines (▲▼ or context) on every KPI card, no dual-axis charts, a category
drill-through and tooltip page, a footer with source/refresh/caveats, a page navigator, alt text and phone layouts."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pbir_kit as k
from pbir_kit import (L, C, col, mea, qref, cat_filter, series_color_by_value, series_color_by_measure, Page,
                      NAVY, TEAL, AMBER, CORAL, SLATE, INK, MUTED, WHITE, W, H, M, G)

ROOT = Path(__file__).resolve().parents[1]
k.init(ROOT / "RetailPulse-PBI.Report")
OUT = ROOT / "analysis" / "output"
BAND = "#9A86E8"        # forecast P10/P90 lines: 3.0:1 on white
GREY = SLATE            # context series (one-time customers): 4.8:1 on white, ΔE 78 from violet under deuteranopia

# ---------------------------------------------------------------- facts for the static plan text (from notebook outputs)
levers = {r["lever"]: r for r in csv.DictReader(open(OUT / "pbi_levers.csv", encoding="utf-8"))}
f26 = {(r["scenario"][0], r["metric"]): r for r in csv.DictReader(open(OUT / "pbi_forecast_2026.csv", encoding="utf-8"))}
lk = lambda x: float(x) / 1e5
cap, act = levers["Discount cap (10%, no stacking)"], levers["Activate 20% of never-ordered"]
rep, rst = levers["Repeat rate 53% to 60%"], levers["Restart sign-ups (2024 pace)"]
base = lk(f26[("A", "Gross profit")]["p50"])
first_lo, first_hi = lk(cap["uplift_low"]) + lk(act["uplift_low"]), lk(cap["uplift_high"]) + lk(act["uplift_high"])
bt = {(r["target"], r["model"]): r for r in csv.DictReader(open(OUT / "forecast_backtest.csv", encoding="utf-8"))}
bt_orders = float(bt[("rev_orders", "Customer-base simulation (median)")]["total_error_pct"])
bt_gp = float(bt[("gross_profit", "Customer-base simulation (median)")]["total_error_pct"])

CT = col("Customers", "Customer Type")
SEG, STATE = col("Customers", "Segment"), col("Customers", "State")
YEAR, YQ, MNO = col("Date", "Year"), col("Date", "Year Quarter"), col("Date", "Month No")
CAT, SUB = col("Products", "Category"), col("Products", "Subcategory")
NO_PURCHASE = cat_filter("excl_no_purchase", "Customers", "Customer Type", ["'No Purchase'"], exclude=True)
CT_COLORS = [series_color_by_value("Customers", "Customer Type", "Recurring", TEAL),
             series_color_by_value("Customers", "Customer Type", "One-Time", GREY)]
NO_AXIS_TITLES = {"categoryAxis": [{"properties": {"showAxisTitle": L(False)}}],
                  "valueAxis": [{"properties": {"showAxisTitle": L(False), "gridlineShow": L(True)}}]}
LABELS = {"labels": [{"properties": {"show": L(True), "fontSize": L(9)}}]}
LEGEND_TOP = {"legend": [{"properties": {"show": L(True), "position": L("Top")}}]}
NO_VALUE_AXIS = {"valueAxis": [{"properties": {"show": L(False)}}]}
Y2025 = [cat_filter("year_2025", "Date", "Year", ["2025L"])]
JAN_OCT = cat_filter("jan_oct", "Date", "Month No", [f"{i}L" for i in range(1, 11)])
FOOTER = mea("Footer Text")
TIP, DT = "category_tip", "category_detail"
NOTOT = {"subTotals": [{"properties": {"rowSubtotals": L(False)}}], "total": [{"properties": {"show": L(False)}}]}
D = lambda m: mea(f"Δ {m}")
DC = lambda m: mea(f"Δ {m} Color")
NEU, WARN = mea("Δ Neutral Color"), mea("Δ Warn Color")

# vertical grid: header 0-72 | cards 80-168 | row 2 | row 3 | footer H-32
row2_y, row2_h = 178, 240
row3_end = H - 38
row3_y = row2_y + row2_h + G
row3_h = row3_end - row3_y
c3 = (W - 2 * M - 2 * G) / 3
x1, x2, x3 = M, round(M + c3 + G), round(M + 2 * (c3 + G))
cw3 = round(c3)


def line_styles(*fields_widths):
    return [{"properties": {"strokeWidth": L(w_), "showMarker": L(mk), **({"lineStyle": L("dashed")} if dash else {})},
             "selector": {"metadata": qref(f)}} for f, w_, mk, dash in fields_widths]


def default_slicer(pg, name, t, c, label, x, w, value):
    flt = {"Version": 2, "From": [{"Name": "s", "Entity": t, "Type": 0}],
           "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": c}}],
                                           "Values": [[{"Literal": {"Value": f"'{value}'"}}]]}}}]}
    pg.slicer(name, col(t, c), label, x, w)
    v = pg.visuals[-1]
    v["visual"]["objects"]["selection"] = [{"properties": {"singleSelect": L(True), "strictSingleSelect": L(True)}}]
    v["visual"]["objects"]["general"] = [{"properties": {"filter": {"filter": flt}}}]


def top_n_filter(name, t, c, measure, n):
    sub = {"Version": 2, "From": [{"Name": "f", "Entity": t, "Type": 0}, {"Name": "m", "Entity": "_Measures", "Type": 0}],
           "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": c}, "Name": "field"}],
           "OrderBy": [{"Direction": 2, "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": measure}}}],
           "Top": n}
    return {"name": name, "field": col(t, c), "type": "TopN", "howCreated": "User",
            "filter": {"Version": 2,
                       "From": [{"Name": "subquery", "Expression": {"Subquery": {"Query": sub}}, "Type": 2}, {"Name": "f", "Entity": t, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": c}}],
                                                       "Table": {"SourceRef": {"Source": "subquery"}}}}}]}}


pages = []
# =====================================================================
# PAGE 1 - Customer retention  (brief Q1)
# =====================================================================
p = Page("customer_retention", "1 Retention")
p.header("53% of buyers came back, and they earn 76% of gross profit",
         "One-time = exactly 1 order  |  Recurring = 2+ orders  |  Lifetime, Jan 2023 to Oct 2025  |  Titles follow the Segment and State filters",
         title_measure=mea("Title Retention"), title_w=870)
p.slicer("slc_segment", SEG, "Segment", 900, 170)
p.slicer("slc_state", STATE, "State", 1086, 178)
p.cards([
    ("card_buyers", mea("Card Buyers"), "Buying customers", D("Buyers"), NEU),
    ("card_repeat", mea("Card Repeat Rate"), "Repeat rate", D("Repeat Rate"), NEU),
    ("card_rec_share", mea("Card Recurring Profit Share"), "Profit from recurring", D("Recurring Profit Share"), NEU),
    ("card_multiplier", mea("Card Value Multiplier"), "Recurring vs one-time", D("Value Multiplier"), NEU),
    ("card_orders", mea("Card Avg Orders"), "Orders per buyer", D("Avg Orders"), NEU),
    ("card_never", mea("Card Never Ordered"), "Never ordered", D("Never Ordered"), WARN),
])
p.add("col_new_buyers", "clusteredColumnChart", x1, row2_y, cw3, row2_h,
      roles={"Category": [YQ], "Y": [(mea("New Buyers"), "New buyers")]},
      title=mea("Title New Buyers"), subtitle="First-time buyers by quarter (first order date)",
      alt="Column chart of first-time buyers by quarter: sign-ups stopped on 25 Sep 2024 and new buyers fell each year.",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(YQ, "Ascending")])
p.add("col_frequency", "clusteredColumnChart", x2, row2_y, cw3, row2_h,
      roles={"Category": [col("Customers", "Order Frequency")], "Y": [(mea("Registered Customers"), "Customers")]},
      title=mea("Title Order Frequency"), subtitle="Buying customers by lifetime order count",
      alt="Column chart of buying customers by lifetime order count, from 1 to 4+ orders.",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(col("Customers", "Order Frequency"), "Ascending")],
      filters=[cat_filter("excl_zero", "Customers", "Order Frequency", ["'0 orders'"], exclude=True)])
p.add("bar_value_per_cust", "clusteredBarChart", x3, row2_y, cw3, row2_h,
      roles={"Category": [CT], "Y": [(mea("Profit per Customer ₹ L"), "Gross profit per customer")]},
      title=mea("Title Value per Customer"), subtitle="Lifetime gross profit per customer, ₹ L",
      alt="Bar chart of lifetime gross profit per customer: recurring customers in violet, one-time in grey.",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": CT_COLORS},
      sort=[(mea("Profit per Customer ₹ L"), "Descending")], filters=[NO_PURCHASE])
p.add("stack_profit_by_year", "columnChart", x1, row3_y, cw3, row3_h,
      roles={"Category": [YEAR], "Y": [(mea("Gross Profit ₹ L"), "Gross profit")], "Series": [CT]},
      title=mea("Title Profit by Type"), subtitle="Gross profit by year, ₹ L  |  2025 = Jan to Oct",
      alt="Stacked columns of gross profit by year, split into recurring (violet) and one-time (grey) customers.",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP, **LABELS, "dataPoint": CT_COLORS,
               "categoryAxis": [{"properties": {"showAxisTitle": L(False), "axisType": L("Categorical")}}]},
      sort=[(YEAR, "Ascending")], filters=[NO_PURCHASE])
p.add("bar_segment_mix", "hundredPercentStackedBarChart", x2, row3_y, cw3, row3_h,
      roles={"Category": [SEG], "Y": [(mea("Registered Customers"), "Customers")], "Series": [CT]},
      title=mea("Title Segment"), subtitle="Share of buying customers by type",
      alt="100% stacked bars of recurring and one-time buyers in each segment.",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP, "labels": [{"properties": {"show": L(True), "fontSize": L(9), "labelPrecision": L(0)}}],
               "dataPoint": CT_COLORS},
      filters=[NO_PURCHASE])
p.textbox("txt_insights", x3, row3_y, cw3, row3_h, "What this tells us (all customers)", [
    ("Retention carries profit: ", "recurring customers are 53% of buyers but earn 76% of gross profit."),
    ("Second orders are slow: ", "the median gap is 254 days, and 54% return within 2 years. Silence is not churn."),
    ("The funnel is empty: ", "no sign-ups since 25 Sep 2024, and 80 registered customers never ordered."),
    ("Action: ", "a second-order nudge for one-time buyers and a first-order offer for the 80."),
], size="9pt")
p.footer(FOOTER)
pages.append(p)

# =====================================================================
# PAGE 2 - Category profitability  (brief Q2)
# =====================================================================
p = Page("category_profit", "2 Profit")
p.header("Beauty leads with ₹76.5 L (27% of profit); margins run 25–27%",
         "Gross profit = net sales after discounts (excl. tax, shipping) minus cost  |  Cancelled and returned orders excluded  |  Right-click a category for detail",
         title_measure=mea("Title Category"), title_w=870)
p.slicer("slc_year", YEAR, "Year", 900, 170)
p.slicer("slc_segment", SEG, "Segment", 1086, 178)
p.cards([
    ("card_gp", mea("Card Gross Profit"), "Gross profit", D("Gross Profit"), DC("Gross Profit")),
    ("card_ns", mea("Card Net Sales"), "Net sales", D("Net Sales"), DC("Net Sales")),
    ("card_gm", mea("Card Gross Margin"), "Gross margin", D("Gross Margin"), DC("Gross Margin")),
    ("card_top", mea("Top Profit Category"), "Top category", D("Top Category"), NEU),
    ("card_low", mea("Lowest Profit Category"), "Lowest category", D("Lowest Category"), NEU),
    ("card_disc", mea("Card Discount Rate"), "Discount rate", D("Discount Rate"), DC("Discount Rate")),
], small=("card_top", "card_low"))
half = (W - 2 * M - G) // 2
p2_h2 = 206                      # five bars need less height; the P&L table below gets the rest
p2_r3 = row2_y + p2_h2 + G
p2_h3 = row3_end - p2_r3
p.add("bar_gp_by_cat", "clusteredBarChart", M, row2_y, half, p2_h2,
      roles={"Category": [CAT], "Y": [(mea("Gross Profit ₹ L"), "Gross profit")]},
      title=mea("Title GP by Category"), subtitle="Gross profit, ₹ L, highest to lowest  |  Hover for detail, right-click to drill through",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(mea("Gross Profit ₹ L"), "Descending")], tooltip_page=TIP,
      alt="Bar chart of gross profit by category in lakh rupees, sorted from highest to lowest.")
p.add("bar_margin_by_cat", "clusteredBarChart", M + half + G, row2_y, W - 2 * M - half - G, p2_h2,
      roles={"Category": [CAT], "Y": [(mea("Gross Margin %"), "Gross margin")]},
      title=mea("Title Margin by Category"), subtitle="Gross margin %, highest to lowest (axis from zero)",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(NAVY)}}]},
      sort=[(mea("Gross Margin %"), "Descending")], tooltip_page=TIP,
      alt="Bar chart of gross margin by category, sorted from highest to lowest; all categories sit between 25% and 27%.")
mxw = 640
p.add("mx_category", "pivotTable", M, p2_r3, mxw, p2_h3,
      roles={"Rows": [CAT],
             "Values": [(mea("Net Sales ₹ L"), "Net sales ₹ L"), (mea("COGS ₹ L"), "COGS ₹ L"), (mea("Gross Profit ₹ L"), "Gross profit ₹ L"),
                        (mea("Gross Margin %"), "Margin"), (mea("Category Profit Share %"), "Share of profit")]},
      title=mea("Title Subcategory"), subtitle="Category P&L, ₹ L  |  Right-click a category for its subcategories",
      objects={"columnHeaders": [{"properties": {"autoSizeColumnWidth": L(True), "fontSize": L(9)}}], "values": [{"properties": {"fontSize": L(9)}}],
               "rowHeaders": [{"properties": {"fontSize": L(9)}}], "total": [{"properties": {"fontSize": L(9)}}]},
      sort=[(mea("Gross Profit ₹ L"), "Descending")],
      alt="Table of net sales, cost, gross profit, margin and profit share by category, expandable to subcategory.")
p.add("col_discount_margin", "clusteredColumnChart", M + mxw + G, p2_r3, W - 2 * M - mxw - G, p2_h3,
      roles={"Category": [col("Order_Items", "Item Discount Band")], "Y": [(mea("Gross Margin %"), "Gross margin")]},
      title=mea("Title Discount"), subtitle="Gross margin % by item-level discount",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(CORAL)}}]},
      sort=[(col("Order_Items", "Item Discount Band"), "Ascending")],
      alt="Column chart of gross margin by item discount: margin falls as the discount deepens.")
p.footer(FOOTER)
pages.append(p)

# =====================================================================
# PAGE 3 - KPI: Profit per Active Customer  (brief Q3)
# =====================================================================
p = Page("kpi_ppac", "3 KPI")
p.header("PPAC is ₹92,868 in 2025 YTD: 1.3% below last year and 6.0% below target",
         "PPAC = gross profit / active customers = orders per customer x order value x margin  |  Target = last year + 5%  |  Cards: Jan–Oct 2025 vs Jan–Oct 2024",
         title_measure=mea("Title KPI"), title_w=1050)
p.slicer("slc_segment", SEG, "Segment", 1086, 178)
p.cards([
    ("card_ppac", mea("Card PPAC"), "PPAC 2025 YTD", D("PPAC"), DC("PPAC")),
    ("card_target", mea("Card PPAC Target"), "Target (last year + 5%)", D("PPAC Target"), mea("KPI Status Color")),
    ("card_orders", mea("Card Orders per Customer"), "Orders per customer", D("Orders per Customer"), DC("Orders per Customer")),
    ("card_aov", mea("Card AOV"), "Average order value", D("AOV"), DC("AOV")),
    ("card_margin", mea("Card Gross Margin"), "Gross margin", D("Gross Margin"), DC("Gross Margin")),
    ("card_active", mea("Card Active Customers"), "Active customers", D("Active Customers"), DC("Active Customers")),
], filters=Y2025)
lw3 = round((W - 2 * M - G) * 0.62)
PPAC, TGT = mea("Profit per Active Customer"), mea("Profit per Active Customer Target")
p.add("line_ppac_qtr", "lineChart", M, row2_y, lw3, row2_h,
      roles={"Category": [YQ], "Y": [(PPAC, "PPAC"), (TGT, "Target (last year + 5%)")]},
      title=mea("Title PPAC Quarter"), subtitle="PPAC (violet) and target (dashed orange), ₹ per active customer, by quarter  |  2025 Q4 = October only",
      objects={"categoryAxis": [{"properties": {"showAxisTitle": L(False)}}],
               "valueAxis": [{"properties": {"showAxisTitle": L(False), "gridlineShow": L(True), "labelDisplayUnits": L(1)}}], **LEGEND_TOP,
               "dataPoint": [series_color_by_measure(PPAC, TEAL), series_color_by_measure(TGT, CORAL)],
               "lineStyles": line_styles((PPAC, 3, True, False), (TGT, 2, True, True))},
      sort=[(YQ, "Ascending")],
      alt="Line chart of PPAC by quarter against its target (last year plus 5%), one value axis in rupees.")
p.add("bar_ppac_segment", "clusteredBarChart", M + lw3 + G, row2_y, W - 2 * M - lw3 - G, row2_h,
      roles={"Category": [SEG], "Y": [(PPAC, "PPAC")]},
      title=mea("Title PPAC Segment"), subtitle="PPAC by segment, ₹, Jan to Oct 2025",
      objects={**NO_AXIS_TITLES, "labels": [{"properties": {"show": L(True), "fontSize": L(9), "labelDisplayUnits": L(1)}}], **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(PPAC, "Descending")], filters=Y2025,
      alt="Bar chart of PPAC by customer segment in 2025.")
p.add("mx_drivers", "pivotTable", M, row3_y, lw3, row3_h,
      roles={"Rows": [YEAR],
             "Values": [(mea("Active Customers"), "Active customers"), (mea("Orders per Active Customer"), "Orders / customer"),
                        (mea("Avg Order Value"), "Order value ₹"), (mea("Gross Margin %"), "Margin"),
                        (PPAC, "PPAC ₹"), (mea("Profit per Active Customer YoY %"), "PPAC vs LY")]},
      title=mea("Title Drivers"), subtitle="Jan to Oct of each year (like-for-like)  |  PPAC = orders per customer x order value x margin",
      objects=NOTOT, sort=[(YEAR, "Ascending")], filters=[JAN_OCT],
      alt="Table of PPAC and its three drivers for January to October of each year.")
p.textbox("txt_kpi", M + lw3 + G, row3_y, W - 2 * M - lw3 - G, row3_h, "Why this KPI", [
    "It joins how often customers buy with what each order earns, in one number that has an owner for each driver.",
    ("Frequency (CRM): ", "repeat-purchase programmes."),
    ("Order value (merchandising): ", "bundles and cross-sell."),
    ("Margin (pricing): ", "discount guardrails."),
    "Read PPAC with total profit: winning back one-time buyers adds profit but can lower PPAC.",
], size="9pt")
p.footer(FOOTER)
pages.append(p)

# =====================================================================
# PAGE 4 - Insights & data notes
# =====================================================================
p = Page("insights", "4 Insights")
p.header("Eight findings, ranked by business impact", "Findings from the Jan 2023 to Oct 2025 order data (all customers, all years)  |  Data and model notes on the right")
fy = 80
fh = H - 38 - fy
p.textbox("txt_findings", M, fy, half, fh, "Business findings", [
    ("1. Sign-ups stopped on 25 Sep 2024. ", "New buyers fell 128 (2023) to 64 (2024) to 28 (2025 YTD), and repeat orders are now 75% of orders. Confirm this is not an extract cut-off."),
    ("2. Profit is flat, not collapsing. ", "Like-for-like (Jan to Oct), gross profit fell 21% in 2024 and rose 6% in 2025. Active customers: 108, 84, 90."),
    ("3. Retention carries the business. ", "Recurring customers are 53% of buyers but earn 76% of gross profit (2.8x a one-time buyer). Second orders are slow: median 254 days."),
    ("4. 80 registered customers never ordered. ", "27% of the base. They look like buyers (same age and segment mix), so a first-order offer is cheap growth."),
    ("5. Discounts cost margin and buy no loyalty. ", "Margin is 30.4% with no item discount but 17.1% at 15%; 29 lines sold below cost. A discounted first order brings no extra repeat buying."),
    ("6. Beauty leads, Home & Kitchen trails. ", "Beauty earns ₹76.5 L (27% of profit), Home & Kitchen ₹48.1 L. Serum is the top subcategory (₹22.3 L)."),
    ("7. Revenue leakage. ", "19 cancelled or returned orders lost ₹52.3 L of sales and ₹12.0 L of profit (4.7% of orders), with no pattern by payment method."),
    ("8. Maharashtra and Gujarat ", "deliver 40% of gross profit, but repeat behaviour does not differ by state: volume is concentrated, behaviour is not."),
], size="11pt", gap=True)
p.textbox("txt_dq", M + half + G, fy, W - 2 * M - half - G, fh, "Data and model notes", [
    ("Duplicate customers fixed. ", "307 rows for 302 IDs: the query keeps the most complete row per ID and drops one stub row, leaving 300 customers. Names, emails and phone numbers are then dropped."),
    ("Missing order dates filled. ", "23 cancelled lines had no order date; each is filled from the other lines of the same order."),
    ("Order totals not loaded. ", "items_total and total_amount repeat on every line (summing them overstates sales about 4.6x). Use Net Sales and Gross Profit."),
    ("Profit definition. ", "Net sales = unit price x qty x (1 - item discount) x (1 - order discount), excl. tax and shipping. COGS = cost price x qty. Cancelled and returned orders excluded."),
    ("Calculations in Power Query. ", "Line amounts are computed at load; one marked Date table (auto date/time off) ends on 31 Oct 2025, so 2025 compares like-for-like."),
    ("SKU prefixes don't match categories, ", "so SKU is not used."),
    ("Synthetic-looking data. ", "Every email is on example.com and buyers behave identically, so the methods transfer but the amounts are illustrative."),
], accent=CORAL, size="11pt", gap=True)
p.footer(FOOTER)
pages.append(p)

# =====================================================================
# PAGE 5 - Forecast & levers (data from analysis/03_forecast and 04_customer_models)
# =====================================================================
p = Page("forecast", "5 Forecast")
p.header("2026 gross profit: about ₹96.9 L (80% range ₹80–115 L) under scenario A",
         "Customer-base simulation, 2,000 runs  |  Median with 80% range (P10 to P90)  |  Cards compare with 2024, the last full year",
         title_measure=mea("Title Forecast"), title_w=790)
default_slicer(p, "slc_scenario", "Scenario", "Scenario", "Acquisition scenario", 820, 250, "A · No new sign-ups")
default_slicer(p, "slc_metric", "Forecast", "Metric", "Chart metric", 1086, 178, "Gross profit")
p.cards([
    ("card_f_gp", mea("Card F26 Gross Profit"), "2026 gross profit", D("F26 Gross Profit"), DC("F26 Gross Profit")),
    ("card_f_range", mea("Card F26 Range"), "80% range", D("F26 Range"), NEU),
    ("card_f_orders", mea("Card F26 Orders"), "2026 revenue orders", D("F26 Orders"), DC("F26 Orders")),
    ("card_f_new", mea("Card F26 New Buyers"), "2026 new buyers", D("F26 New Buyers"), DC("F26 New Buyers")),
    ("card_f_ppac", mea("Card F26 PPAC"), "2026 PPAC", D("F26 PPAC"), DC("F26 PPAC")),
    ("card_f_prob", mea("Card F26 Hit Chance"), "Hits PPAC target", D("F26 Hit Chance"), NEU),
])
FA, F50, F10, F90 = mea("Fcst Actual"), mea("Fcst P50"), mea("Fcst P10"), mea("Fcst P90")
p.add("line_forecast", "lineChart", M, row2_y, W - 2 * M, row2_h,
      roles={"Category": [col("Forecast", "Month")],
             "Y": [(FA, "Actual"), (F50, "Forecast (median)"), (F10, "Low case (P10)"), (F90, "High case (P90)")]},
      title="Monthly history and forecast: single months swing, so plan on quarterly totals",
      subtitle=(f"₹ L for gross profit and net sales, counts for orders and buyers  |  Backtest on 6 held-out months: orders {bt_orders:+.1%}, "
                f"gross profit {bt_gp:+.1%}, both inside the 80% range"),
      objects={**NO_AXIS_TITLES, **LEGEND_TOP,
               "categoryAxis": [{"properties": {"showAxisTitle": L(False), "axisType": L("Scalar")}}],
               "dataPoint": [series_color_by_measure(FA, NAVY), series_color_by_measure(F50, TEAL),
                             series_color_by_measure(F10, BAND), series_color_by_measure(F90, BAND)],
               "lineStyles": line_styles((FA, 2, False, False), (F50, 3, False, False), (F10, 1, False, True), (F90, 1, False, True))},
      sort=[(col("Forecast", "Month"), "Ascending")],
      alt="Line chart of monthly history (navy) and the 2026 forecast median (violet) with dashed low and high cases.")
lw = round((W - 2 * M - G) * 0.55)
p.add("bar_levers", "clusteredBarChart", M, row3_y, lw, row3_h,
      roles={"Category": [col("Levers", "Lever")], "Y": [(mea("Lever Uplift ₹ L"), "2026 profit uplift (mid)")],
             "Tooltips": [(mea("Lever Uplift Low ₹ L"), "Low"), (mea("Lever Uplift High ₹ L"), "High")]},
      title=mea("Title Levers"), subtitle="Mid estimate of extra 2026 gross profit, ₹ L  |  Confidence and cost in the plan  |  Hover for low and high",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(mea("Lever Uplift ₹ L"), "Descending")],
      alt="Bar chart of four 2026 profit levers with their mid uplift in lakh rupees, confidence and cost.")
p.textbox("txt_plan", M + lw + G, row3_y, W - 2 * M - lw - G, row3_h,
          f"Recommended plan: start with the two cheap levers (₹{first_lo:.0f}–{first_hi:.0f} L)", [
    ("1. Pricing: ", f"cap item discounts at 10% and stop stacking (+₹{lk(cap['uplift_low']):.1f}–{lk(cap['uplift_high']):.1f} L, high confidence, no cost)."),
    ("2. CRM: ", f"first-order offer to the 80 never-ordered (+₹{lk(act['uplift_low']):.1f}–{lk(act['uplift_high']):.1f} L, medium, low cost)."),
    ("3. CRM: ", f"second-order nudge, repeat rate 53% to 60% (+₹{lk(rep['uplift_mid']):.1f} L; lowers PPAC)."),
    ("4. Marketing: ", f"find out why sign-ups stopped before spending on them (+₹{lk(rst['uplift_mid']):.1f} L at the 2024 pace)."),
    ("Size: ", f"levers 1+2 add {first_lo / base:.0%}–{first_hi / base:.0%} to the ₹{base:.1f} L baseline (scenario A). Levers overlap, so don't add all four."),
], size="9pt")
p.footer(FOOTER)
pages.append(p)

# =====================================================================
# Category detail: drill-through page (right-click a category)
# =====================================================================
DT_FILTER = "dt_category"
p = Page(DT, "Category detail", page_type="Drillthrough", hidden=True,
         binding={"name": "category_detail_binding", "type": "Drillthrough",
                  "parameters": [{"name": "category_param", "boundFilter": DT_FILTER, "fieldExpr": CAT}]},
         filters=[{"name": DT_FILTER, "field": CAT, "type": "Categorical", "howCreated": "Drillthrough"}])
p.header("Category detail", "Drill-through page: one category against all products  |  Keeps the Year and Segment filters  |  Back button (Ctrl+click in Desktop) to return",
         title_measure=mea("Title Category Detail"), title_w=1080)
p.add("btn_back", "actionButton", W - M - 120, 18, 120, 36, alt="Back to the previous page",
      objects={"icon": [{"properties": {"shapeType": L("back")}, "selector": {"id": "default"}}],
               "text": [{"properties": {"show": L(True), "text": L("Back"), "fontColor": C(WHITE)}, "selector": {"id": "default"}}]},
      container={"visualLink": [{"properties": {"show": L(True), "type": L("Back")}}],
                 "background": [{"properties": {"show": L(False)}}], "border": [{"properties": {"show": L(False)}}],
                 "title": [{"properties": {"show": L(False)}}]})
p.cards([
    ("card_cat", mea("Selected Category"), "Category"),
    ("card_cat_gp", mea("Card Gross Profit"), "Gross profit", D("Gross Profit"), DC("Gross Profit")),
    ("card_cat_share", mea("Card Category Share"), "Share of profit", D("Category Share"), NEU),
    ("card_cat_margin", mea("Card Gross Margin"), "Gross margin", D("Category Margin"), NEU),
    ("card_cat_disc", mea("Card Discount Rate"), "Discount rate", D("Discount Rate"), DC("Discount Rate")),
    ("card_cat_loss", mea("Card Loss Lines"), "Lines sold below cost", D("Loss Lines"), WARN),
], small=("card_cat",))
p.add("bar_sub_gp", "clusteredBarChart", M, row2_y, half, row2_h,
      roles={"Category": [SUB], "Y": [(mea("Gross Profit ₹ L"), "Gross profit")]},
      title="Gross profit by subcategory", subtitle="₹ L, highest to lowest",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(mea("Gross Profit ₹ L"), "Descending")])
p.add("col_cat_discount", "clusteredColumnChart", M + half + G, row2_y, W - 2 * M - half - G, row2_h,
      roles={"Category": [col("Order_Items", "Item Discount Band")], "Y": [(mea("Gross Margin %"), "Gross margin")]},
      title="Gross margin by item discount", subtitle="Margin % for this category at each item discount",
      objects={**NO_AXIS_TITLES, **LABELS, **NO_VALUE_AXIS, "dataPoint": [{"properties": {"fill": C(CORAL)}}]},
      sort=[(col("Order_Items", "Item Discount Band"), "Ascending")])
p.add("col_cat_qtr", "clusteredColumnChart", M, row3_y, half, row3_h,
      roles={"Category": [YQ], "Y": [(mea("Gross Profit ₹ L"), "Gross profit")]},
      title="Gross profit by quarter", subtitle="₹ L  |  2025 Q4 = October only",
      objects={**NO_AXIS_TITLES, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(YQ, "Ascending")])
PNAME = col("Products", "Product Name")
p.add("tbl_top_products", "tableEx", M + half + G, row3_y, W - 2 * M - half - G, row3_h,
      roles={"Values": [PNAME, (mea("Gross Profit ₹ L"), "Gross profit ₹ L"), (mea("Gross Margin %"), "Margin"), (mea("Units Sold"), "Units")]},
      title="Top 5 products by gross profit", subtitle="Revenue orders only",
      objects={"values": [{"properties": {"fontSize": L(10)}}], "total": [{"properties": {"totals": L(False)}}]},
      sort=[(mea("Gross Profit ₹ L"), "Descending")], filters=[top_n_filter("top5_products", "Products", "Product Name", "Gross Profit", 5)])
p.footer(FOOTER, nav=False)
pages.append(p)

# =====================================================================
# Category tooltip: report-page tooltip on the category charts
# =====================================================================
TW, TH = 400, 300
p = Page(TIP, "Category tooltip", page_type="Tooltip", hidden=True, binding={"name": "category_tip_binding", "type": "Tooltip"}, size=(TW, TH))
p.cards([("tip_cat", mea("Selected Category"), "Category"), ("tip_share", mea("Card Category Share"), "Share of profit")],
        y=6, h=64, x0=8, width=TW - 16)
p.cards([("tip_gp", mea("Card Gross Profit"), "Gross profit"), ("tip_margin", mea("Card Gross Margin"), "Margin"),
         ("tip_top", mea("Top Subcategory"), "Top subcategory")], y=76, h=64, x0=8, width=TW - 16)
p.add("tip_line", "lineChart", 8, 146, TW - 16, TH - 152,
      roles={"Category": [YQ], "Y": [(mea("Gross Profit ₹ L"), "Gross profit")]},
      title="Gross profit by quarter (₹ L)", container={"subTitle": [{"properties": {"show": L(False)}}],
                                                         "padding": [{"properties": {"top": L(4), "bottom": L(4), "left": L(6), "right": L(6)}}]},
      objects={**NO_AXIS_TITLES, "dataPoint": [{"properties": {"fill": C(TEAL)}}], "lineStyles": [{"properties": {"strokeWidth": L(2)}}],
               "categoryAxis": [{"properties": {"show": L(False)}}]},
      sort=[(YQ, "Ascending")])
for v in p.visuals:   # compact text for the small canvas
    if v["visual"]["visualType"] == "cardVisual":
        v["visual"]["objects"]["value"] = [{"properties": {"fontSize": L(12)}, "selector": {"id": "default"}}]
        v["visual"]["objects"]["label"] = [{"properties": {"fontSize": L(8)}, "selector": {"id": "default"}}]
pages.append(p)

# keep the Segment slicer in sync across pages 1-3
for pg in pages:
    for v in pg.visuals:
        if v["name"] == "slc_segment":
            v["visual"]["syncGroup"] = {"groupName": "Segment", "fieldChanges": True, "filterChanges": True}
k.finish(pages)
