"""Generate the RetailPulse-PBI dashboard pages as PBIR JSON."""
import json, shutil, sys
from pathlib import Path

REPORT = Path(sys.argv[1])  # ...\RetailPulse-PBI.Report
DEF = REPORT / "definition"
PAGES = DEF / "pages"
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# ---------- palette ----------
# InXiteOut brand (inxiteout.ai): deep navy, violet primary, lilac secondary; orange for warnings
NAVY, TEAL, AMBER, CORAL, SLATE, GREEN = "#030734", "#682EFF", "#CD83FF", "#F05100", "#62748E", "#009588"
FONT, FONT_BOLD = "'Instrument Sans', 'Segoe UI', sans-serif", "'Instrument Sans', 'Segoe UI Semibold', sans-serif"
INK, MUTED, BG, LINE, WHITE = "#020618", "#62748E", "#F1F5F9", "#E2E8F0", "#FFFFFF"
W, H, M, G = 1280, 720, 16, 12  # page size, margin, gutter


# ---------- literal helpers ----------
def L(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def C(hex_):
    return {"solid": {"color": L(hex_)}}


def col(t, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def mea(c, t="_Measures"):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def proj(field, display=None):
    kind = "Column" if "Column" in field else "Measure"
    t = field[kind]["Expression"]["SourceRef"]["Entity"]
    c = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{t}.{c}", "nativeQueryRef": c}
    if kind == "Column":
        p["active"] = True
    if display:
        p["displayName"] = display
    return p


def qref(field):
    kind = "Column" if "Column" in field else "Measure"
    return f'{field[kind]["Expression"]["SourceRef"]["Entity"]}.{field[kind]["Property"]}'


def cat_filter(name, t, c, values, exclude=False):
    cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": c}}],
                   "Values": [[{"Literal": {"Value": v}}] for v in values]}}
    if exclude:
        cond = {"Not": {"Expression": cond}}
    return {"name": name, "field": col(t, c), "type": "Categorical", "howCreated": "User",
            "filter": {"Version": 2, "From": [{"Name": "s", "Entity": t, "Type": 0}], "Where": [{"Condition": cond}]}}


def series_color_by_value(t, c, value, hex_):
    return {"properties": {"fill": C(hex_)},
            "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col(t, c),
                                                               "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}}


def series_color_by_measure(field, hex_):
    return {"properties": {"fill": C(hex_)}, "selector": {"metadata": qref(field)}}


# ---------- page builder ----------
class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals, self.z = name, display, [], 0

    def add(self, name, vtype, x, y, w, h, roles=None, title=None, subtitle=None, objects=None,
            sort=None, filters=None, container=None):
        vis = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if roles is not None:
            vis["query"] = {"queryState": {r: {"projections": [proj(*f) if isinstance(f, tuple) else proj(f) for f in fs]}
                                           for r, fs in roles.items()}}
            if sort:
                vis["query"]["sortDefinition"] = {"sort": [{"field": f, "direction": d} for f, d in sort],
                                                  "isDefaultSort": False}
        if objects:
            vis["objects"] = objects
        vco = {}
        if title is not None:
            vco["title"] = [{"properties": {"show": L(True), "text": L(title), "fontSize": L(11),
                                            "fontColor": C(INK), "bold": L(True)}}]
        if subtitle:
            vco["subTitle"] = [{"properties": {"show": L(True), "text": L(subtitle), "fontSize": L(9),
                                               "fontColor": C(MUTED)}}]
        vco.update(container or {})
        if vco:
            vis["visualContainerObjects"] = vco
        v = {"$schema": VC_SCHEMA, "name": name,
             "position": {"x": x, "y": y, "z": self.z * 1000, "height": h, "width": w, "tabOrder": self.z * 1000},
             "visual": vis}
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.z += 1
        self.visuals.append(v)
        return v

    # --- composite helpers ---
    def header(self, title, subtitle, width=W - 2 * M):
        self.add("hdr_band", "textbox", 0, 0, W, 72, objects={"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": title, "textStyle": {"fontWeight": "bold", "fontSize": "18pt", "color": WHITE,
                                                          "fontFamily": FONT_BOLD}}]},
            {"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "10pt", "color": "#C8C3F5"}}]}]}}]},
            container={"background": [{"properties": {"show": L(True), "color": C(NAVY), "transparency": L(0)}}],
                       "border": [{"properties": {"show": L(False)}}],
                       "padding": [{"properties": {"top": L(8), "left": L(16)}}]})

    def slicer(self, name, field, label, x, w):
        self.add(name, "slicer", x, 8, w, 56, roles={"Values": [field]},
                 objects={"data": [{"properties": {"mode": L("Dropdown")}}],
                          "header": [{"properties": {"show": L(True), "text": L(label), "fontColor": C(MUTED),
                                                     "textSize": L(9)}}],
                          "items": [{"properties": {"fontColor": C(INK), "textSize": L(10)}}]},
                 container={"background": [{"properties": {"show": L(True), "color": C(WHITE), "transparency": L(0)}}],
                            "border": [{"properties": {"show": L(True), "color": C(LINE), "radius": L(6)}}],
                            "padding": [{"properties": {"top": L(2), "bottom": L(2), "left": L(8), "right": L(8)}}]})

    def cards(self, items, y=84, h=88, filters=None, small=()):
        n = len(items)
        cw = (W - 2 * M - (n - 1) * G) / n
        for i, (name, field, label) in enumerate(items):
            self.add(name, "cardVisual", round(M + i * (cw + G)), y, round(cw), h,
                     roles={"Data": [(field, label)]}, filters=filters,
                     objects={"accentBar": [{"properties": {"show": L(True), "color": C(TEAL if i % 2 == 0 else AMBER)},
                                             "selector": {"id": "default"}}],
                              "label": [{"properties": {"fontSize": L(10)}, "selector": {"id": "default"}}],
                              "value": [{"properties": {"fontSize": L(14 if name in small else 24)}, "selector": {"id": "default"}}]})

    def textbox(self, name, x, y, w, h, title, lines, accent=TEAL, size="10pt", gap=False):
        lines = [tuple(s.replace("Rs ", "₹") for s in ln) if isinstance(ln, tuple) else ln.replace("Rs ", "₹")
                 for ln in lines]
        paras = [{"textRuns": [{"value": title, "textStyle": {"fontWeight": "bold", "fontSize": "12pt", "color": INK,
                                                              "fontFamily": FONT_BOLD}}]}]
        for ln in lines:
            if isinstance(ln, tuple):  # (bold lead, rest)
                paras.append({"textRuns": [
                    {"value": ln[0], "textStyle": {"fontWeight": "bold", "fontSize": size, "color": accent}},
                    {"value": ln[1], "textStyle": {"fontSize": size, "color": INK}}]})
            else:
                paras.append({"textRuns": [{"value": ln, "textStyle": {"fontSize": size, "color": INK}}]})
            if gap:
                paras.append({"textRuns": [{"value": "", "textStyle": {"fontSize": "6pt"}}]})
        self.add(name, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paras}}]},
                 container={"padding": [{"properties": {"top": L(10), "left": L(14), "right": L(14)}}]})

    def write(self):
        pdir = PAGES / self.name
        if pdir.exists():
            shutil.rmtree(pdir)
        (pdir / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE_SCHEMA, "name": self.name, "displayName": self.display, "displayOption": "FitToPage",
                "height": H, "width": W,
                "objects": {"background": [{"properties": {"color": C(BG), "transparency": L(0)}}],
                            "outspace": [{"properties": {"color": C(BG)}}]}}
        (pdir / "page.json").write_text(json.dumps(page, indent=2), encoding="utf-8")
        for v in self.visuals:
            d = pdir / "visuals" / v["name"]
            d.mkdir()
            (d / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- common fields ----------
CT = col("Customers", "Customer Type")
SEG = col("Customers", "segment")
STATE = col("Customers", "state")
YEAR = col("Date", "Year")
YQ = col("Date", "Year Quarter")
CAT = col("Products", "category")
SUB = col("Products", "subcategory")
NO_PURCHASE = cat_filter("excl_no_purchase", "Customers", "Customer Type", ["'No Purchase'"], exclude=True)
CT_COLORS = [series_color_by_value("Customers", "Customer Type", "Recurring", TEAL),
             series_color_by_value("Customers", "Customer Type", "One-Time", AMBER)]
NO_AXIS_TITLES = {"categoryAxis": [{"properties": {"showAxisTitle": L(False)}}],
                  "valueAxis": [{"properties": {"showAxisTitle": L(False), "gridlineShow": L(True)}}]}
LABELS = {"labels": [{"properties": {"show": L(True), "fontSize": L(9)}}]}
LEGEND_TOP = {"legend": [{"properties": {"show": L(True), "position": L("Top")}}]}

pages = []
row2_y, row2_h = 184, 262
row3_y = row2_y + row2_h + G
row3_h = H - M - row3_y

# =====================================================================
# PAGE 1 - Customer retention
# =====================================================================
p = Page("customer_retention", "1. Customer Retention")
p.header("Customer Retention: One-Time vs Recurring",
         "One-time = exactly 1 order placed  |  Recurring = 2+ orders  |  Orders Jan 2023 to Oct 2025")
p.slicer("slc_segment", SEG, "Segment", 900, 170)
p.slicer("slc_state", STATE, "State", 1086, 178)
p.cards([
    ("card_purchasing", mea("Purchasing Customers"), "Buying Customers"),
    ("card_onetime", mea("One-Time Customers", "Customers"), "One-Time"),
    ("card_recurring", mea("Recurring Customers", "Customers"), "Recurring"),
    ("card_recurring_pct", mea("Recurring Customer %", "Customers"), "Repeat Rate"),
    ("card_orders_per_cust", mea("Avg Orders per Customer"), "Orders / Customer"),
    ("card_never", mea("Never-Purchased Customers"), "Never Ordered"),
])
# fix entity for Customers-table measures
for v in p.visuals:
    for r in v["visual"].get("query", {}).get("queryState", {}).values():
        for pr in r["projections"]:
            m = pr["field"].get("Measure")
            if m and m["Property"] == "Purchasing Customers":
                m["Expression"]["SourceRef"]["Entity"] = "Customers"
                pr["queryRef"] = "Customers.Purchasing Customers"

c3 = (W - 2 * M - 2 * G) / 3
x1, x2, x3 = M, round(M + c3 + G), round(M + 2 * (c3 + G))
p.add("donut_mix", "donutChart", x1, row2_y, round(c3), row2_h,
      roles={"Category": [CT], "Y": [(mea("Registered Customers"), "Customers")]},
      title="Customer mix", subtitle="Share of purchasing customers by lifetime orders",
      objects={**LEGEND_TOP, "labels": [{"properties": {"show": L(True), "labelStyle": L("Category, percent of total"),
                                                           "fontSize": L(10)}}],
               "dataPoint": CT_COLORS},
      filters=[NO_PURCHASE])
p.add("col_frequency", "clusteredColumnChart", x2, row2_y, round(c3), row2_h,
      roles={"Category": [col("Customers", "Order Frequency")], "Y": [(mea("Registered Customers"), "Customers")]},
      title="How many orders do customers place?", subtitle="Customers by lifetime order count",
      objects={**NO_AXIS_TITLES, **LABELS, "dataPoint": [{"properties": {"fill": C(TEAL)}}]},
      sort=[(col("Customers", "Order Frequency"), "Ascending")],
      filters=[cat_filter("excl_zero", "Customers", "Order Frequency", ["'0 orders'"], exclude=True)])
p.add("bar_value_per_cust", "clusteredBarChart", x3, row2_y, round(c3), row2_h,
      roles={"Category": [CT], "Y": [(mea("Profit per Active Customer"), "Gross profit per customer")]},
      title="Recurring customers are worth ~2.8x more",
      subtitle="Lifetime gross profit per customer",
      objects={**NO_AXIS_TITLES, **LABELS, "dataPoint": CT_COLORS,
               "valueAxis": [{"properties": {"show": L(False)}}]},
      sort=[(mea("Profit per Active Customer"), "Descending")], filters=[NO_PURCHASE])
p.add("stack_profit_by_year", "columnChart", x1, row3_y, round(c3), row3_h,
      roles={"Category": [YEAR], "Y": [(mea("Gross Profit"), "Gross Profit")], "Series": [CT]},
      title="Profit by customer type", subtitle="Recurring customers drive ~76% of gross profit",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP, "dataPoint": CT_COLORS,
               "categoryAxis": [{"properties": {"showAxisTitle": L(False), "axisType": L("Categorical")}}]},
      sort=[(YEAR, "Ascending")], filters=[NO_PURCHASE])
p.add("bar_segment_mix", "hundredPercentStackedBarChart", x2, row3_y, round(c3), row3_h,
      roles={"Category": [SEG], "Y": [(mea("Registered Customers"), "Customers")], "Series": [CT]},
      title="Retention by segment", subtitle="Share of purchasing customers",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP, **LABELS, "dataPoint": CT_COLORS},
      filters=[NO_PURCHASE])
p.textbox("txt_insights", x3, row3_y, round(c3), row3_h, "What this tells us", [
    ("52.7% ", "of buyers came back (116 recurring vs 104 one-time)."),
    ("76% ", "of gross profit comes from recurring customers."),
    ("2.8x: ", "a recurring customer brings Rs 1.88 L profit vs Rs 0.68 L for a one-time buyer."),
    ("80 customers ", "(27% of the base) registered but never ordered, an easy activation target."),
    ("Action: ", "a second-order nudge for one-time buyers is the biggest profit lever."),
])
pages.append(p)

# =====================================================================
# PAGE 2 - Category profitability
# =====================================================================
p = Page("category_profit", "2. Category Profitability")
p.header("Category Profitability",
         "Gross profit = net sales (after item and order discounts, excl. tax and shipping) minus cost  |  Cancelled and returned orders excluded")
p.slicer("slc_year", YEAR, "Year", 900, 170)
p.slicer("slc_segment", SEG, "Segment", 1086, 178)
p.cards([
    ("card_gp", mea("Gross Profit"), "Gross Profit"),
    ("card_ns", mea("Net Sales"), "Net Sales"),
    ("card_gm", mea("Gross Margin %"), "Gross Margin %"),
    ("card_top", mea("Top Profit Category"), "Top Category"),
    ("card_low", mea("Lowest Profit Category"), "Lowest Category"),
    ("card_disc", mea("Discount Rate %"), "Discount Rate"),
], small=("card_top", "card_low"))
c2a = round((W - 2 * M - G) * 0.42)
c2b = W - 2 * M - G - c2a
p.add("bar_gp_by_cat", "clusteredBarChart", M, row2_y, c2a, row2_h,
      roles={"Category": [CAT], "Y": [(mea("Gross Profit"), "Gross Profit")]},
      title="Gross profit by category", subtitle="Ranked highest to lowest",
      objects={**NO_AXIS_TITLES, **LABELS, "dataPoint": [{"properties": {"fill": C(TEAL)}}],
               "valueAxis": [{"properties": {"show": L(False)}}]},
      sort=[(mea("Gross Profit"), "Descending")])
p.add("combo_sales_margin", "lineClusteredColumnComboChart", M + c2a + G, row2_y, c2b, row2_h,
      roles={"Category": [CAT], "Y": [(mea("Net Sales"), "Net Sales"), (mea("Gross Profit"), "Gross Profit")],
             "Y2": [(mea("Gross Margin %"), "Gross Margin %")]},
      title="Sales, profit and margin by category", subtitle="Columns: net sales and gross profit  |  Line: gross margin %",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP,
               "dataPoint": [series_color_by_measure(mea("Net Sales"), "#D9CCFF"),
                             series_color_by_measure(mea("Gross Profit"), TEAL),
                             series_color_by_measure(mea("Gross Margin %"), AMBER)],
               "lineStyles": [{"properties": {"strokeWidth": L(3), "showMarker": L(True)}}]},
      sort=[(mea("Net Sales"), "Descending")])
p.add("mx_category", "pivotTable", M, row3_y, c2a + 150, row3_h,
      objects={"columnHeaders": [{"properties": {"autoSizeColumnWidth": L(True)}}], "values": [{"properties": {"fontSize": L(10)}}]},
      roles={"Rows": [CAT, SUB],
             "Values": [(mea("Net Sales"), "Net Sales"), (mea("COGS"), "COGS"), (mea("Gross Profit"), "Gross Profit"),
                        (mea("Gross Margin %"), "Margin %"), (mea("Category Profit Share %"), "Profit Share")]},
      title="Category and subcategory P&L", subtitle="Expand a category to see its subcategories",
      sort=[(mea("Gross Profit"), "Descending")])
p.add("col_discount_margin", "clusteredColumnChart", M + c2a + 150 + G, row3_y, c2b - 150, row3_h,
      roles={"Category": [col("Order_Items", "Item Discount Band")], "Y": [(mea("Gross Margin %"), "Gross Margin %")]},
      title="Deeper discounts erode margin", subtitle="Gross margin % by item-level discount",
      objects={**NO_AXIS_TITLES, **LABELS, "dataPoint": [{"properties": {"fill": C(CORAL)}}]},
      sort=[(col("Order_Items", "Item Discount Band"), "Ascending")])
pages.append(p)

# =====================================================================
# PAGE 3 - KPI: Profit per Active Customer
# =====================================================================
p = Page("kpi_ppac", "3. KPI: Profit per Customer")
p.header("KPI: Profit per Active Customer (PPAC)",
         "Gross profit / customers with a revenue order  |  Target = same period last year + 5%  |  Cards show 2025 YTD (Jan to Oct) vs Jan to Oct 2024")
p.slicer("slc_segment", SEG, "Segment", 1086, 178)
Y2025 = [cat_filter("year_2025", "Date", "Year", ["2025L"])]
p.cards([
    ("card_ppac", mea("Profit per Active Customer"), "PPAC 2025 YTD"),
    ("card_target", mea("Profit per Active Customer Target"), "Target (PY + 5%)"),
    ("card_vs_target", mea("KPI vs Target %"), "vs Target"),
    ("card_yoy", mea("Profit per Active Customer YoY %"), "vs Last Year"),
    ("card_status", mea("KPI Status"), "Status"),
    ("card_active", mea("Active Customers"), "Active Cust. 2025"),
], filters=Y2025, small=("card_status",))
for v in p.visuals:
    if v["name"] == "card_status":
        v["visual"]["objects"]["value"] = [{"properties": {"fontSize": L(16),
                                                           "fontColor": {"solid": {"color": {"expr": mea("KPI Status Color")}}}},
                                            "selector": {"id": "default"}}]
        v["visual"]["objects"]["accentBar"] = [{"properties": {"show": L(True), "color": {"solid": {"color": {"expr": mea("KPI Status Color")}}}},
                                                "selector": {"id": "default"}}]
kw = 300
p.add("kpi_ppac", "kpi", M, row2_y, kw, row2_h,
      roles={"Indicator": [(mea("Profit per Active Customer"), "PPAC")],
             "Goal": [(mea("Profit per Active Customer Target"), "Target")],
             "TrendLine": [YEAR]},
      title="PPAC vs target", subtitle="Latest year (2025 YTD) against goal",
      objects={"goals": [{"properties": {"showGoal": L(True), "showDistance": L(True)}}],
               "trendline": [{"properties": {"show": L(False)}}]},
      sort=[(YEAR, "Ascending")])
p.add("combo_ppac_qtr", "lineClusteredColumnComboChart", M + kw + G, row2_y, W - 2 * M - kw - G, row2_h,
      roles={"Category": [YQ], "Y": [(mea("Profit per Active Customer"), "PPAC")],
             "Y2": [(mea("Profit per Active Customer Target"), "Target (PY + 5%)")]},
      title="PPAC by quarter vs target", subtitle="2025 Q4 contains October only",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP,
               "dataPoint": [series_color_by_measure(mea("Profit per Active Customer"), TEAL),
                             series_color_by_measure(mea("Profit per Active Customer Target"), CORAL)],
               "lineStyles": [{"properties": {"strokeWidth": L(2), "lineStyle": L("dashed"), "showMarker": L(True)}}]},
      sort=[(YQ, "Ascending")])
mw = 700
p.add("mx_drivers", "pivotTable", M, row3_y, mw, row3_h,
      roles={"Rows": [YEAR],
             "Values": [(mea("Active Customers"), "Active Cust."), (mea("Orders per Active Customer"), "Orders / Cust."),
                        (mea("Avg Order Value"), "Avg Order Value"), (mea("Gross Margin %"), "Margin %"),
                        (mea("Profit per Active Customer"), "PPAC"), (mea("Profit per Active Customer YoY %"), "PPAC YoY")]},
      title="What drives PPAC", subtitle="PPAC = Orders per customer x Avg order value x Margin %",
      sort=[(YEAR, "Ascending")])
p.textbox("txt_kpi", M + mw + G, row3_y, W - 2 * M - mw - G, row3_h, "Why this KPI", [
    "It joins customer behaviour (how often people buy) with profitability (what each order earns) in one number.",
    ("2025 YTD: ", "Rs 92,868 per customer, 1.3% below last year and 6% below target."),
    ("Driver: ", "vs Jan to Oct 2024, orders per customer fell 1.32 to 1.27 and avg order value fell Rs 2.86 L to Rs 2.73 L. Margin improved 24.9% to 26.8% but could not offset it."),
    ("Levers: ", "repeat-purchase programmes (frequency), bundles (order value), discount guardrails (margin)."),
    "Edit the measure [KPI Target Growth %] to change the target.",
])
pages.append(p)

# =====================================================================
# PAGE 4 - Insights & data notes
# =====================================================================
p = Page("insights", "4. Key Insights")
p.header("Key Insights and Data Notes", "Findings from the Jan 2023 to Oct 2025 order data, ranked by business impact")
half = (W - 2 * M - G) // 2
p.textbox("txt_findings", M, 80, half, H - 80 - M, "Business findings", [
    ("1. Sign-ups stopped on 25 Sep 2024. ", "With no new registrations since, new buyers fell 128 (2023) to 64 (2024) to 28 (2025 YTD) and repeat orders are now 75% of orders. Confirm this is not an extract cut-off."),
    ("2. Profit is flat, not collapsing. ", "Like-for-like (Jan to Oct), gross profit fell 21% in 2024 and rose 6% in 2025. Active customers: 108, 84, 90."),
    ("3. Retention carries the business. ", "Recurring customers are 53% of buyers but 76% of gross profit (2.8x a one-time buyer). Second orders are slow: median 254 days."),
    ("4. 80 registered customers never ordered. ", "27% of the base. They look like buyers (same age and segment mix), so a first-order offer is cheap growth."),
    ("5. Discounts cost margin and do not buy loyalty. ", "Margin is 30.4% with no item discount but 17.1% at 15%; 29 lines sold below cost. A discounted first order brings no extra repeat buying."),
    ("6. Beauty leads, Home & Kitchen trails. ", "Beauty earns Rs 76.5 L (27% of profit), Home & Kitchen Rs 48.1 L. Serum is the top subcategory (Rs 22.3 L)."),
    ("7. Revenue leakage. ", "19 cancelled or returned orders lost Rs 52.3 L in sales and Rs 12.0 L in profit (4.7% of orders), with no significant pattern by payment method."),
    ("8. Maharashtra and Gujarat ", "deliver 40% of gross profit, but repeat behaviour does not differ by state: volume is concentrated, behaviour is not."),
], accent=TEAL, size="11pt", gap=True)
p.textbox("txt_dq", M + half + G, 80, W - 2 * M - half - G, H - 80 - M, "Data and model notes", [
    ("Duplicate customers fixed. ", "The Customers sheet had 307 rows for 302 IDs (CUST0001 x4, CUST0300 x3, one blank ID). The query keeps the most complete row per ID and drops one stub row (CUST0301, first name only): 300 customers."),
    ("Missing order dates filled. ", "23 cancelled lines had no order_date; each is filled from the other lines of the same order."),
    ("Relationship fixed. ", "Customers to Order_Items was many-to-many and bi-directional. It is now one-to-many, single direction."),
    ("Do not sum items_total or total_amount. ", "They are order-level values repeated on every line; summing them overstates sales about 4.6x. Use the Net Sales and Gross Profit measures."),
    ("Profit definition. ", "Net sales = unit price x qty x (1 - item discount) x (1 - order discount), excluding tax and shipping. COGS = cost price x qty. Cancelled and returned orders are excluded."),
    ("SKU prefixes do not match categories ", "(for example Fashion products with BE- SKUs). Do not use SKU to infer category."),
    ("Date table added ", "and marked; it ends on the last order date (31 Oct 2025), so 2025 vs 2024 comparisons are like-for-like."),
    ("No cost data for shipping or marketing, ", "so profit here is gross profit, not net profit."),
], accent=CORAL, size="11pt", gap=True)
pages.append(p)


# =====================================================================
# PAGE 5 - Forecast & levers (data from analysis/03_forecast and 04_customer_models)
# =====================================================================
def default_slicer(pg, name, t, c, label, x, w, value):
    flt = {"Version": 2, "From": [{"Name": "s", "Entity": t, "Type": 0}],
           "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": c}}],
                                           "Values": [[{"Literal": {"Value": f"'{value}'"}}]]}}}]}
    pg.add(name, "slicer", x, 8, w, 56, roles={"Values": [col(t, c)]},
           objects={"data": [{"properties": {"mode": L("Dropdown")}}],
                    "selection": [{"properties": {"singleSelect": L(True), "strictSingleSelect": L(True)}}],
                    "general": [{"properties": {"filter": {"filter": flt}}}],
                    "header": [{"properties": {"show": L(True), "text": L(label), "fontColor": C(MUTED), "textSize": L(9)}}],
                    "items": [{"properties": {"fontColor": C(INK), "textSize": L(10)}}]},
           container={"background": [{"properties": {"show": L(True), "color": C(WHITE), "transparency": L(0)}}],
                      "border": [{"properties": {"show": L(True), "color": C(LINE), "radius": L(6)}}],
                      "padding": [{"properties": {"top": L(2), "bottom": L(2), "left": L(8), "right": L(8)}}]})

p = Page("forecast", "5. Forecast & Levers")
p.header("Forecast 2026 and Profit Levers",
         "Customer-base simulation, 2,000 runs  |  Median with 80% range (P10-P90)  |  Source: analysis/03_forecast, 04_customer_models")
default_slicer(p, "slc_scenario", "Scenario", "Scenario", "Acquisition scenario", 820, 250, "A · No new sign-ups")
default_slicer(p, "slc_metric", "Forecast", "metric", "Chart metric", 1086, 178, "Gross profit")
p.cards([
    ("card_f_gp", mea("F26 Gross Profit (L)"), "2026 Gross Profit"),
    ("card_f_range", mea("F26 Gross Profit Range"), "80% Range"),
    ("card_f_orders", mea("F26 Revenue Orders"), "2026 Revenue Orders"),
    ("card_f_new", mea("F26 New Buyers"), "2026 New Buyers"),
    ("card_f_ppac", mea("F26 PPAC"), "2026 PPAC"),
    ("card_f_prob", mea("F26 P(PPAC hits target)"), "Hits PPAC Target"),
], small=("card_f_range",))
FA, F50, F10, F90 = mea("Fcst Actual"), mea("Fcst P50"), mea("Fcst P10"), mea("Fcst P90")
p.add("line_forecast", "lineChart", M, row2_y, W - 2 * M, row2_h,
      roles={"Category": [col("Forecast", "month")],
             "Y": [(FA, "Actual"), (F50, "Forecast (median)"), (F10, "Low case (P10)"), (F90, "High case (P90)")]},
      title="Monthly history and forecast", subtitle="Single months are noisy (about 41% swing); plan on quarterly or annual totals",
      objects={**NO_AXIS_TITLES, **LEGEND_TOP,
               "categoryAxis": [{"properties": {"showAxisTitle": L(False), "axisType": L("Continuous")}}],
               "dataPoint": [series_color_by_measure(FA, NAVY), series_color_by_measure(F50, TEAL),
                             series_color_by_measure(F10, "#D9CCFF"), series_color_by_measure(F90, "#D9CCFF")],
               "lineStyles": [{"properties": {"strokeWidth": L(2)}, "selector": {"metadata": qref(FA)}},
                              {"properties": {"strokeWidth": L(3)}, "selector": {"metadata": qref(F50)}},
                              {"properties": {"strokeWidth": L(1), "lineStyle": L("dashed")}, "selector": {"metadata": qref(F10)}},
                              {"properties": {"strokeWidth": L(1), "lineStyle": L("dashed")}, "selector": {"metadata": qref(F90)}}]},
      sort=[(col("Forecast", "month"), "Ascending")])
lw = round((W - 2 * M - G) * 0.55)
p.add("bar_levers", "clusteredBarChart", M, row3_y, lw, row3_h,
      roles={"Category": [col("Levers", "lever")], "Y": [(mea("Lever Uplift"), "2026 profit uplift (mid)")],
             "Tooltips": [(mea("Lever Uplift Low"), "Low"), (mea("Lever Uplift High"), "High")]},
      title="Profit levers for 2026", subtitle="Mid estimate of extra gross profit; hover for low and high",
      objects={**NO_AXIS_TITLES, **LABELS, "dataPoint": [{"properties": {"fill": C(AMBER)}}],
               "valueAxis": [{"properties": {"show": L(False)}}]},
      sort=[(mea("Lever Uplift"), "Descending")])
p.textbox("txt_forecast_notes", M + lw + G, row3_y, W - 2 * M - lw - G, row3_h, "How to read this page", [
    ("Plan on about Rs 1 crore ", "of 2026 gross profit, with Rs 80 L as the downside, under any acquisition scenario."),
    ("PPAC target is unlikely ", "(about 20-24% chance). It only moves with orders per customer, order value and margin."),
    ("Levers stack: ", "a 10% discount cap with no stacking is the safest (re-pricing only); activating the 80 never-ordered is the largest."),
    ("All buyers behave alike ", "(one ~3.6%/month rate), so treat them equally: no propensity targeting."),
    ("To update: ", "re-run analysis notebooks 03 and 04, then refresh this report."),
])
pages.append(p)

# ---------- write pages ----------
for pg in pages:
    pg.write()

pj = PAGES / "pages.json"
meta = json.loads(pj.read_text(encoding="utf-8"))
old = [n for n in meta["pageOrder"] if n not in {pg.name for pg in pages}]
meta["pageOrder"] = [pg.name for pg in pages] + old
meta["activePageName"] = pages[0].name
pj.write_text(json.dumps(meta, indent=2), encoding="utf-8")

# ---------- theme ----------
theme = {
    "name": "InXiteOut",
    "dataColors": [TEAL, AMBER, NAVY, CORAL, SLATE, GREEN, "#AC24FF", "#FCBB00"],
    "foreground": INK, "foregroundNeutralSecondary": MUTED, "background": WHITE, "backgroundLight": BG,
    "tableAccent": TEAL, "good": GREEN, "neutral": AMBER, "bad": CORAL,
    "textClasses": {
        "title": {"fontFace": FONT_BOLD, "fontSize": 11, "color": INK},
        "label": {"fontFace": FONT, "fontSize": 10, "color": MUTED},
        "callout": {"fontFace": FONT_BOLD, "fontSize": 24, "color": NAVY},
        "header": {"fontFace": FONT_BOLD, "fontSize": 11, "color": INK},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": WHITE}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": LINE}}, "radius": 8, "width": 1}],
            "dropShadow": [{"show": False}],
            "title": [{"show": True, "fontColor": {"solid": {"color": INK}}, "fontSize": 11, "fontFamily": FONT_BOLD}],
            "padding": [{"top": 8, "bottom": 8, "left": 12, "right": 12}],
        }},
        "page": {"*": {"background": [{"color": {"solid": {"color": BG}}, "transparency": 0}]}},
        "pivotTable": {"*": {
            "columnHeaders": [{"backColor": {"solid": {"color": NAVY}}, "fontColor": {"solid": {"color": WHITE}}, "fontSize": 10}],
            "values": [{"fontSize": 10, "backColorSecondary": {"solid": {"color": "#F6F3FF"}}}],
            "subTotals": [{"rowSubtotals": True}],
            "total": [{"fontColor": {"solid": {"color": NAVY}}}],
        }},
    },
}
rr = REPORT / "StaticResources" / "RegisteredResources"
rr.mkdir(parents=True, exist_ok=True)
(rr / "InxiteOut.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")

rj = DEF / "report.json"
rep = json.loads(rj.read_text(encoding="utf-8"))
base = rep["themeCollection"]["baseTheme"]
rep["themeCollection"]["customTheme"] = {"name": "InxiteOut.json", "reportVersionAtImport": base["reportVersionAtImport"],
                                         "type": "RegisteredResources"}
pk = [r for r in rep["resourcePackages"] if r["name"] != "RegisteredResources"]
pk.append({"name": "RegisteredResources", "type": "RegisteredResources",
           "items": [{"name": "InxiteOut.json", "path": "InxiteOut.json", "type": "CustomTheme"}]})
rep["resourcePackages"] = pk
rj.write_text(json.dumps(rep, indent=2), encoding="utf-8")
print("pages:", [pg.name for pg in pages], "visuals:", sum(len(pg.visuals) for pg in pages))
