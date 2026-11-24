"""Writes the RetailPulse-PBI semantic model (TMDL) from one specification.
Run with Power BI Desktop CLOSED on this project:  python _build/make_semantic_model.py
Then open the .pbip in Desktop and Refresh.

v2 (Nov 2026, after the dashboard scorecard review):
- Auto date/time off (no hidden LocalDateTable copies); one marked Date table.
- Line calculations (gross amount, net sales, COGS, gross profit, revenue flag, bands) moved from DAX columns into
  Power Query; COGS no longer uses RELATED.
- Title Case column names, fixed decimal instead of floating point, keys marked, foreign keys hidden, geographic
  categories, and a description on every visible table, column and measure.
- Personal fields (names, email, phone) are used only to pick the most complete duplicate row, then dropped.
- Display measures (card text in Indian units, change lines with arrows and AA colours, footer) and action-title
  measures that follow the slicers.
Rules mirror analysis/src/metrics.py."""
import json
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "RetailPulse-PBI"
DEFN = Path(os.environ.get("RP_DEFN") or ROOT / f"{NAME}.SemanticModel" / "definition")   # RP_DEFN: write elsewhere (push_measures.py)
T = "\t"
RUPEE = "₹"


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def lt() -> str:
    return f"lineageTag: {uuid.uuid4()}"


q = lambda n: f"'{n}'" if any(ch in n for ch in " -&()%") else n
ind = lambda m, n: "\n".join(T * n + ln for ln in m.splitlines())

# ---------------------------------------------------------------- clean out the old model files
for f in (DEFN / "tables").glob("*.tmdl"):
    f.unlink()                                   # includes the LocalDateTable / DateTableTemplate copies
w(DEFN / "cultures" / "en-IN.tmdl", "cultureInfo en-IN\n")   # old linguistic metadata named the old columns

TABLES = ["Customers", "Products", "Order_Items", "Date", "_Measures", "Forecast", "Forecast 2026", "Levers", "Scenario",
          "Refresh Info"]
w(DEFN / "model.tmdl",
  "model Model\n\tculture: en-IN\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-IN\n"
  "\tvalueFilterBehavior: independent\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
  "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
  'annotation PBI_QueryOrder = ["ProjectFolder","SourceWorkbook","ProductsRef","Customers","Products","Order_Items","Forecast","Forecast 2026","Levers"]\n\n'
  'annotation PBI_ProTooling = ["DevMode"]\n\n'
  + "".join(f"ref table {q(t)}\n" for t in TABLES) + "\nref cultureInfo en-IN\n")


# ---------------------------------------------------------------- parameters + shared products query
def param(name, value):
    return (f'expression {name} = "{value}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
            f"{T}{lt()}\n\n{T}annotation PBI_NavigationStepName = Navigation\n\n{T}annotation PBI_ResultType = Text\n\n")


old_expr = (DEFN / "expressions.tmdl").read_text(encoding="utf-8")
src_wb = old_expr.split('expression SourceWorkbook = "', 1)[1].split('"', 1)[0] if "SourceWorkbook" in old_expr else ""
products_m = """let
    Source = Excel.Workbook(File.Contents(SourceWorkbook), null, true),
    Sheet = Source{[Item = "Products", Kind = "Sheet"]}[Data],
    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"product_id", type text}, {"sku", type text}, {"product_name", type text}, {"category", type text}, {"subcategory", type text}, {"unit_price", Currency.Type}, {"cost_price", Currency.Type}, {"supplier", type text}, {"stock_quantity", Int64.Type}}, "en-US")
in
    Typed"""
w(DEFN / "expressions.tmdl",
  param("ProjectFolder", str(ROOT)) + param("SourceWorkbook", src_wb)
  + f"/// Products sheet as typed (not loaded): feeds the Products table and the cost price in Order_Items.\nexpression ProductsRef =\n{ind(products_m, 3)}\n"
  + f"{T}{lt()}\n\n{T}annotation PBI_ResultType = Table\n")


# ---------------------------------------------------------------- column / table writers
def column(name, dtype, desc, fmt=None, hidden=False, key=False, category=None, folder=None, sort_by=None, expr=None,
           source=None, inferred=False):
    """One TMDL column. expr = DAX calculated column; inferred = column of a calculated table."""
    s = f"{T}/// {desc}\n" if desc else ""
    s += f"{T}column {q(name)}" + (f" = {expr}" if expr else "") + "\n" + (f"{T * 2}dataType: {dtype}\n" if dtype else "")
    if fmt: s += f"{T * 2}formatString: {fmt}\n"
    if hidden: s += f"{T * 2}isHidden\n"
    if key: s += f"{T * 2}isKey\n"
    if category: s += f"{T * 2}dataCategory: {category}\n"
    if folder: s += f"{T * 2}displayFolder: {folder}\n"
    if sort_by: s += f"{T * 2}sortByColumn: {q(sort_by)}\n"
    if hidden and not key: s += f"{T * 2}isAvailableInMdx: false\n"
    s += f"{T * 2}{lt()}\n{T * 2}summarizeBy: none\n"
    if inferred: s += f"{T * 2}isNameInferred\n{T * 2}sourceColumn: [{name}]\n"
    elif not expr: s += f"{T * 2}sourceColumn: {source or name}\n"
    return s + f"\n{T * 2}annotation SummarizationSetBy = User\n\n"


def m_table(name, desc, cols, m, extra=""):
    s = f"/// {desc}\ntable {q(name)}\n{T}{lt()}\n\n" + "".join(column(*c[:3], **(c[3] if len(c) > 3 else {})) for c in cols)
    s += extra
    s += f"{T}partition {q(name)} = m\n{T * 2}mode: import\n{T * 2}source =\n{ind(m, 4)}\n\n{T}annotation PBI_ResultType = Table\n"
    w(DEFN / "tables" / f"{name}.tmdl", s)


def rename(pairs):
    return ", ".join('{"%s", "%s"}' % p for p in pairs)


# ---------------------------------------------------------------- Customers
CUST_RN = [("customer_id", "Customer ID"), ("join_date", "Join Date"), ("city", "City"), ("state", "State"), ("country", "Country"),
           ("segment", "Segment"), ("gender", "Gender"), ("birth_date", "Birth Date")]
customers_m = f"""let
    Source = Excel.Workbook(File.Contents(SourceWorkbook), null, true),
    Sheet = Source{{[Item = "Customers", Kind = "Sheet"]}}[Data],
    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{{{"customer_id", type text}}, {{"first_name", type text}}, {{"last_name", type text}}, {{"email", type text}}, {{"phone", Int64.Type}}, {{"join_date", type date}}, {{"city", type text}}, {{"state", type text}}, {{"country", type text}}, {{"segment", type text}}, {{"gender", type text}}, {{"birth_date", type date}}}}, "en-US"),
    NoBlankIds = Table.SelectRows(Typed, each [customer_id] <> null and [customer_id] <> ""),
    Completeness = Table.AddColumn(NoBlankIds, "__filled", each List.NonNullCount(Record.FieldValues(_)), Int64.Type),
    Sorted = Table.Buffer(Table.Sort(Completeness, {{{{"customer_id", Order.Ascending}}, {{"__filled", Order.Descending}}}})),
    MostComplete = Table.Distinct(Sorted, {{"customer_id"}}),
    NoStubs = Table.SelectRows(MostComplete, each not ([email] = null and [join_date] = null and [segment] = null)),
    NoPersonalData = Table.RemoveColumns(NoStubs, {{"__filled", "first_name", "last_name", "email", "phone"}}),
    Renamed = Table.RenameColumns(NoPersonalData, {{{rename(CUST_RN)}}})
in
    Renamed"""
LIFE = "Customer Behaviour"
cust_cols = [
    ("Customer ID", "string", "Customer identifier (key). Duplicates in the source are collapsed to the most complete row.", {"key": True}),
    ("Join Date", "dateTime", "Date the customer registered. The last sign-up is 25 Sep 2024.", {"fmt": "dd-mmm-yyyy"}),
    ("City", "string", "Customer city.", {"category": "City"}),
    ("State", "string", "Customer state.", {"category": "StateOrProvince"}),
    ("Country", "string", "Customer country (all India).", {"category": "Country"}),
    ("Segment", "string", "Retail or Wholesale.", {}),
    ("Gender", "string", "Gender as recorded.", {}),
    ("Birth Date", "dateTime", "Date of birth (feeds Age Group).", {"fmt": "dd-mmm-yyyy"}),
    ("Lifetime Orders", "int64", "Orders ever placed, any status (0 = registered but never ordered).",
     {"fmt": "0", "folder": LIFE, "expr": "CALCULATE ( DISTINCTCOUNT ( Order_Items[Order ID] ) ) + 0"}),
    ("Customer Type", "string", "No Purchase (0 orders), One-Time (1) or Recurring (2+), over the customer's lifetime.",
     {"folder": LIFE, "expr": 'SWITCH ( TRUE (), Customers[Lifetime Orders] = 0, "No Purchase", Customers[Lifetime Orders] = 1, "One-Time", "Recurring" )'}),
    ("Order Frequency", "string", "Lifetime order count as a band: 0, 1, 2, 3 or 4+ orders.",
     {"folder": LIFE, "expr": 'SWITCH ( TRUE (), Customers[Lifetime Orders] = 0, "0 orders", Customers[Lifetime Orders] = 1, "1 order", '
                             'Customers[Lifetime Orders] = 2, "2 orders", Customers[Lifetime Orders] = 3, "3 orders", "4+ orders" )'}),
    ("Lifetime Gross Profit", "decimal", "Gross profit from the customer's revenue orders.",
     {"fmt": f"{RUPEE}#,##0", "folder": LIFE, "expr": "CALCULATE ( SUM ( Order_Items[Gross Profit] ), Order_Items[Is Revenue Order] = TRUE () )"}),
    ("First Order Date", "dateTime", "Date of the customer's first order (any status).",
     {"fmt": "dd-mmm-yyyy", "folder": LIFE, "expr": "CALCULATE ( MIN ( Order_Items[Order Date] ) )"}),
    ("Last Order Date", "dateTime", "Date of the customer's latest order (any status).",
     {"fmt": "dd-mmm-yyyy", "folder": LIFE, "expr": "CALCULATE ( MAX ( Order_Items[Order Date] ) )"}),
    ("Age Group", "string", "Age band on 31 Oct 2025 (the last order date).",
     {"folder": LIFE, "expr": 'VAR a = DATEDIFF ( Customers[Birth Date], DATE ( 2025, 10, 31 ), YEAR ) RETURN SWITCH ( TRUE (), ISBLANK ( Customers[Birth Date] ), "Unknown", '
                             'a < 25, "18-24", a < 35, "25-34", a < 45, "35-44", a < 55, "45-54", "55+" )'}),
]
m_table("Customers", "Customer dimension: 300 customers after removing duplicate and stub rows.", cust_cols, customers_m)

# ---------------------------------------------------------------- Products
PROD_RN = [("product_id", "Product ID"), ("product_name", "Product Name"), ("category", "Category"), ("subcategory", "Subcategory"),
           ("supplier", "Supplier")]
products_tbl_m = f"""let
    Source = ProductsRef,
    Kept = Table.SelectColumns(Source, {{"product_id", "product_name", "category", "subcategory", "supplier"}}),
    Renamed = Table.RenameColumns(Kept, {{{rename(PROD_RN)}}})
in
    Renamed"""
m_table("Products", "Product dimension. SKU prefixes don't match categories, so SKU is not loaded.", [
    ("Product ID", "string", "Product identifier (key).", {"key": True}),
    ("Product Name", "string", "Product name.", {}),
    ("Category", "string", "Product category (5).", {}),
    ("Subcategory", "string", "Product subcategory.", {}),
    ("Supplier", "string", "Supplier name.", {}),
], products_tbl_m)

# ---------------------------------------------------------------- Order_Items fact
OI_RN = [("order_item_id", "Order Item ID"), ("order_id", "Order ID"), ("order_date", "Order Date"), ("customer_id", "Customer ID"),
         ("order_status", "Order Status"), ("payment_method", "Payment Method"), ("discount_percent", "Order Discount %"),
         ("product_id", "Product ID"), ("quantity", "Quantity"), ("unit_price", "Unit Price"), ("item_discount_percent", "Item Discount %")]
oi_m = f"""let
    Source = Excel.Workbook(File.Contents(SourceWorkbook), null, true),
    Sheet = Source{{[Item = "Order_Items", Kind = "Sheet"]}}[Data],
    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{{{"order_item_id", type text}}, {{"order_id", type text}}, {{"order_date", type date}}, {{"customer_id", type text}}, {{"order_status", type text}}, {{"payment_method", type text}}, {{"discount_percent", Int64.Type}}, {{"product_id", type text}}, {{"quantity", Int64.Type}}, {{"unit_price", Currency.Type}}, {{"item_discount_percent", Int64.Type}}}}, "en-US"),
    Kept = Table.SelectColumns(Typed, {{"order_item_id", "order_id", "order_date", "customer_id", "order_status", "payment_method", "discount_percent", "product_id", "quantity", "unit_price", "item_discount_percent"}}),
    OrderDates = Table.Buffer(Table.Group(Kept, {{"order_id"}}, {{{{"__order_date", each List.Max([order_date]), type nullable date}}}})),
    JoinDates = Table.NestedJoin(Kept, {{"order_id"}}, OrderDates, {{"order_id"}}, "__od", JoinKind.LeftOuter),
    ExpDates = Table.ExpandTableColumn(JoinDates, "__od", {{"__order_date"}}),
    FilledDates = Table.ReplaceValue(ExpDates, each [order_date], each if [order_date] = null then [__order_date] else [order_date], Replacer.ReplaceValue, {{"order_date"}}),
    Retyped = Table.TransformColumnTypes(FilledDates, {{{{"order_date", type date}}}}),
    Costs = Table.Buffer(Table.SelectColumns(ProductsRef, {{"product_id", "cost_price"}})),
    JoinCost = Table.NestedJoin(Retyped, {{"product_id"}}, Costs, {{"product_id"}}, "__p", JoinKind.LeftOuter),
    ExpCost = Table.ExpandTableColumn(JoinCost, "__p", {{"cost_price"}}),
    Gross = Table.AddColumn(ExpCost, "Gross Amount", each [unit_price] * [quantity], Currency.Type),
    Net = Table.AddColumn(Gross, "Net Sales", each [unit_price] * [quantity] * (1 - [item_discount_percent] / 100) * (1 - [discount_percent] / 100), Currency.Type),
    Cogs = Table.AddColumn(Net, "COGS", each [cost_price] * [quantity], Currency.Type),
    Profit = Table.AddColumn(Cogs, "Gross Profit", each [Net Sales] - [COGS], Currency.Type),
    Revenue = Table.AddColumn(Profit, "Is Revenue Order", each not List.Contains({{"Cancelled", "Returned"}}, [order_status]), type logical),
    StatusGroup = Table.AddColumn(Revenue, "Order Status Group", each if [Is Revenue Order] then "Fulfilled / In Progress" else "Cancelled / Returned", type text),
    ItemBand = Table.AddColumn(StatusGroup, "Item Discount Band", each Text.From([item_discount_percent]) & "% item disc.", type text),
    OrderBand = Table.AddColumn(ItemBand, "Order Discount Band", each Text.From([discount_percent]) & "% order disc.", type text),
    Cleaned = Table.RemoveColumns(OrderBand, {{"__order_date", "cost_price"}}),
    Renamed = Table.RenameColumns(Cleaned, {{{rename(OI_RN)}}})
in
    Renamed"""
CALC = "Calculated"
m_table("Order_Items", "Order-line fact: 1,500 lines. Amounts exclude tax and shipping; the order-level totals in the source "
        "(items_total, total_amount) repeat on every line and are not loaded.", [
    ("Order Item ID", "string", "Order line identifier.", {}),
    ("Order ID", "string", "Order identifier (an order has one or more lines).", {}),
    ("Order Date", "dateTime", "Order date; 23 missing dates on cancelled lines are filled from the same order.", {"fmt": "dd-mmm-yyyy", "hidden": True}),
    ("Customer ID", "string", "Customer key.", {"hidden": True}),
    ("Order Status", "string", "Delivered, Shipped, Processing, Cancelled or Returned.", {}),
    ("Payment Method", "string", "Payment method.", {}),
    ("Order Discount %", "int64", "Order-level discount in percent.", {"fmt": "0"}),
    ("Product ID", "string", "Product key.", {"hidden": True}),
    ("Quantity", "int64", "Units on the line.", {"fmt": "#,##0"}),
    ("Unit Price", "decimal", "List price per unit.", {"fmt": f"{RUPEE}#,##0.00"}),
    ("Item Discount %", "int64", "Item-level discount in percent.", {"fmt": "0"}),
    ("Gross Amount", "decimal", "Unit price x quantity, before discounts.", {"fmt": f"{RUPEE}#,##0.00", "hidden": True, "folder": CALC}),
    ("Net Sales", "decimal", "Gross amount after item and order discounts (excl. tax and shipping).", {"fmt": f"{RUPEE}#,##0.00", "hidden": True, "folder": CALC}),
    ("COGS", "decimal", "Product cost price x quantity.", {"fmt": f"{RUPEE}#,##0.00", "hidden": True, "folder": CALC}),
    ("Gross Profit", "decimal", "Net sales minus COGS.", {"fmt": f"{RUPEE}#,##0.00", "hidden": True, "folder": CALC}),
    ("Is Revenue Order", "boolean", "FALSE for cancelled and returned orders.", {"folder": CALC}),
    ("Order Status Group", "string", "Fulfilled / In Progress, or Cancelled / Returned.", {"folder": CALC}),
    ("Item Discount Band", "string", "Item discount as a label, e.g. 10% item disc.", {"folder": CALC, "sort_by": "Item Discount %"}),
    ("Order Discount Band", "string", "Order discount as a label, e.g. 5% order disc.", {"folder": CALC, "sort_by": "Order Discount %"}),
], oi_m)

# ---------------------------------------------------------------- Date (calculated, ends on the last order date)
date_dax = ('ADDCOLUMNS ( CALENDAR ( DATE ( YEAR ( MIN ( Order_Items[Order Date] ) ), 1, 1 ), MAX ( Order_Items[Order Date] ) ), '
            '"Year", YEAR ( [Date] ), "Quarter", "Q" & QUARTER ( [Date] ), "Year Quarter", YEAR ( [Date] ) & " Q" & QUARTER ( [Date] ), '
            '"Month No", MONTH ( [Date] ), "Month", FORMAT ( [Date], "MMM" ), "Month Start", DATE ( YEAR ( [Date] ), MONTH ( [Date] ), 1 ), '
            '"Year Month", FORMAT ( [Date], "MMM yy" ), "Year Month Key", YEAR ( [Date] ) * 100 + MONTH ( [Date] ) )')
dcols = [("Date", "dateTime", "Calendar date (key).", {"fmt": "dd-mmm-yyyy", "key": True}),
         ("Year", "int64", "Calendar year.", {"fmt": "0"}),
         ("Quarter", "string", "Calendar quarter, Q1-Q4.", {}),
         ("Year Quarter", "string", "Year and quarter, e.g. 2025 Q3.", {}),
         ("Month No", "int64", "Month number, 1-12 (sorts Month).", {"fmt": "0"}),
         ("Month", "string", "Month name, e.g. Jan.", {"sort_by": "Month No"}),
         ("Month Start", "dateTime", "First day of the month.", {"fmt": "mmm yyyy"}),
         ("Year Month", "string", "Month label, e.g. Jan 25.", {"sort_by": "Year Month Key"}),
         ("Year Month Key", "int64", "yyyymm number (sorts Year Month).", {"fmt": "0"})]
ds = f"/// Calendar from 1 Jan 2023 to the last order date (31 Oct 2025), so 2025 compares like-for-like with Jan-Oct 2024. Marked date table.\ntable Date\n{T}{lt()}\n{T}dataCategory: Time\n\n"
ds += "".join(column(n, d, desc, inferred=True, **kw) for n, d, desc, kw in dcols)
ds += f"{T}partition Date = calculated\n{T * 2}mode: import\n{T * 2}source = {date_dax}\n"
w(DEFN / "tables" / "Date.tmdl", ds)

# ---------------------------------------------------------------- forecast + levers (from analysis notebooks 03 and 04)
BS = chr(92)
CSV_RN = {"scenario": "Scenario", "month": "Month", "metric": "Metric", "kind": "Kind", "actual": "Actual", "p10": "P10", "p50": "P50",
          "p90": "P90", "lever": "Lever", "uplift_low": "Uplift Low", "uplift_high": "Uplift High", "uplift_mid": "Uplift Mid",
          "confidence": "Confidence", "cost": "Cost", "basis": "Basis"}


def csv_table(name, file, desc, cols, blanks=(), extra=""):
    mt = {"string": "type text", "dateTime": "type date", "decimal": "Currency.Type"}   # fixed decimal, not floating point
    types = ", ".join('{"%s", %s}' % (c, mt[d]) for c, d, *_ in cols)
    blank = ('    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {%s}),\n' % ", ".join('"%s"' % b for b in blanks)
             if blanks else "    Blanks = Promoted,\n")
    m = ("let\n"
         f'    Source = Csv.Document(File.Contents(ProjectFolder & "{BS}analysis{BS}output{BS}{file}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n'
         "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n" + blank +
         f'    Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US"),\n'
         '    Renamed = Table.RenameColumns(Typed, {%s})\nin\n    Renamed' % rename([(c, CSV_RN[c]) for c, *_ in cols]))
    m_table(name, f"{desc} From analysis/output/{file}: re-run the notebooks, then refresh.",
            [(CSV_RN[c], d, cd, kw) for c, d, cd, kw in cols], m, extra)


csv_table("Forecast", "pbi_forecast.csv", "Monthly history (Jan 2023-Oct 2025) and simulated forecast (Nov 2025-Dec 2026) by scenario and metric.", [
    ("scenario", "string", "Acquisition scenario (relates to Scenario).", {"hidden": True}),
    ("month", "dateTime", "Month of the history or forecast value.", {"fmt": "mmm yyyy"}),
    ("metric", "string", "Gross profit, Net sales, Revenue orders or New buyers.", {}),
    ("kind", "string", "Actual or Forecast row.", {}),
    ("actual", "decimal", "Actual monthly value (history rows).", {"fmt": "#,##0"}),
    ("p10", "decimal", "Forecast low case (10th percentile of 2,000 runs).", {"fmt": "#,##0"}),
    ("p50", "decimal", "Forecast median.", {"fmt": "#,##0"}),
    ("p90", "decimal", "Forecast high case (90th percentile).", {"fmt": "#,##0"}),
], blanks=("actual", "p10", "p50", "p90"))
csv_table("Forecast 2026", "pbi_forecast_2026.csv", "2026 totals by scenario: orders, sales, profit, new buyers, PPAC and the chance of hitting the PPAC target.", [
    ("scenario", "string", "Acquisition scenario (relates to Scenario).", {"hidden": True}),
    ("metric", "string", "2026 total being forecast.", {}),
    ("p10", "decimal", "Low case (10th percentile).", {"fmt": "#,##0.##"}),
    ("p50", "decimal", "Median.", {"fmt": "#,##0.##"}),
    ("p90", "decimal", "High case (90th percentile).", {"fmt": "#,##0.##"}),
])
csv_table("Levers", "pbi_levers.csv", "Four 2026 profit levers with low/mid/high uplift, confidence and cost.", [
    ("lever", "string", "Profit lever.", {}),
    ("uplift_low", "decimal", "Low estimate of extra 2026 gross profit, in rupees.", {"fmt": f"{RUPEE}#,##0"}),
    ("uplift_high", "decimal", "High estimate of extra 2026 gross profit, in rupees.", {"fmt": f"{RUPEE}#,##0"}),
    ("confidence", "string", "Confidence in the sizing.", {}),
    ("cost", "string", "Cost to run the lever.", {}),
    ("basis", "string", "How the lever was sized.", {}),
    ("uplift_mid", "decimal", "Mid estimate of extra 2026 gross profit, in rupees.", {"fmt": f"{RUPEE}#,##0"}),
])
w(DEFN / "tables" / "Scenario.tmdl",
  f"/// Shared scenario list so one slicer filters both forecast tables.\ntable Scenario\n{T}{lt()}\n\n"
  + column("Scenario", "string", "Acquisition scenario: A no new sign-ups, B sign-ups resume, C activation push.", key=True, inferred=True)
  + f"{T}partition Scenario = calculated\n{T * 2}mode: import\n{T * 2}source = DISTINCT ( SELECTCOLUMNS ( 'Forecast 2026', \"Scenario\", 'Forecast 2026'[Scenario] ) )\n")
w(DEFN / "tables" / "Refresh Info.tmdl",
  f"/// When the model was last refreshed (calculated at refresh time), for the report footer.\ntable 'Refresh Info'\n{T}isHidden\n{T}{lt()}\n\n"
  + column("Refreshed", "dateTime", "", fmt="dd-mmm-yyyy", hidden=True, inferred=True)
  + f"{T}partition 'Refresh Info' = calculated\n{T * 2}mode: import\n{T * 2}source = ROW ( \"Refreshed\", NOW () )\n\n"
  + f'{T}annotation BestPracticeAnalyzer_IgnoreRules = {{"RuleIDs":["ENSURE_TABLES_HAVE_RELATIONSHIPS"]}}\n')

# ---------------------------------------------------------------- relationships
w(DEFN / "relationships.tmdl",
  "relationship Order_Items_Customers\n\tfromColumn: Order_Items.'Customer ID'\n\ttoColumn: Customers.'Customer ID'\n\n"
  "relationship Order_Items_Products\n\tfromColumn: Order_Items.'Product ID'\n\ttoColumn: Products.'Product ID'\n\n"
  "relationship Order_Items_Date\n\tfromColumn: Order_Items.'Order Date'\n\ttoColumn: Date.Date\n\n"
  "relationship Forecast_Scenario\n\tfromColumn: Forecast.Scenario\n\ttoColumn: Scenario.Scenario\n\n"
  "relationship Forecast2026_Scenario\n\tfromColumn: 'Forecast 2026'.Scenario\n\ttoColumn: Scenario.Scenario\n")

# ================================================================ measures
R0, PCT, INT, D2 = f"{RUPEE}#,##0", "0.0%", "#,##0", "0.00"
LAKH = f"{RUPEE}#,##0.0 \\L"
LAKH2 = f"{RUPEE}#,##0.00 \\L"
REV = "Order_Items[Is Revenue Order] = TRUE ()"
NOREV = "Order_Items[Is Revenue Order] = FALSE ()"
PY = lambda m: f"CALCULATE ( {m}, SAMEPERIODLASTYEAR ( 'Date'[Date] ) )"
UP, DOWN = "▲ ", "▼ "
GOOD, BAD, WARN, NEUTRAL = "#1E7F4B", "#C0392B", "#A15F00", "#5B6B7F"     # WCAG AA (>= 4.5:1) on white for small text
PERIOD = "Jan 2023 – Oct 2025"


def inr(x, v="v"):
    """DAX text in Indian units: under ₹1 L in full rupees, ₹1-10 L with two decimals, then ₹ L, then ₹ Cr (crore)."""
    v = f"_{v}"
    return (f"( VAR {v} = {x} RETURN SWITCH ( TRUE (), ISBLANK ( {v} ), BLANK (), "
            f'ABS ( {v} ) >= 10000000, FORMAT ( DIVIDE ( {v}, 10000000 ), "{RUPEE}#,##0.00", "en-US" ) & " Cr", '
            f'ABS ( {v} ) >= 1000000, FORMAT ( DIVIDE ( {v}, 100000 ), "{RUPEE}#,##0.0", "en-US" ) & " L", '
            f'ABS ( {v} ) >= 100000, FORMAT ( DIVIDE ( {v}, 100000 ), "{RUPEE}#,##0.00", "en-US" ) & " L", '
            f'FORMAT ( {v}, "{RUPEE}#,##0", "en-US" ) ) )')


def lakh2(x):
    """DAX text in lakh with two decimals, for side-by-side per-customer values."""
    return f'FORMAT ( DIVIDE ( {x}, 100000 ), "{RUPEE}#,##0.00", "en-US" ) & " L"'


M = []


def add(folder, name, expr, fmt, desc):
    assert desc, f"measure {name} needs a description"
    M.append((name, expr, fmt, folder, desc))


S = "1 Sales & Profit"
add(S, "Net Sales", f"CALCULATE ( SUM ( Order_Items[Net Sales] ), {REV} )", R0,
    "Revenue excluding tax and shipping, after item and order discounts. Excludes cancelled and returned orders.")
add(S, "Gross Sales (List Price)", f"CALCULATE ( SUM ( Order_Items[Gross Amount] ), {REV} )", R0,
    "Unit price x quantity before any discount. Excludes cancelled and returned orders.")
add(S, "COGS", f"CALCULATE ( SUM ( Order_Items[COGS] ), {REV} )", R0, "Product cost price x quantity for revenue orders.")
add(S, "Gross Profit", f"CALCULATE ( SUM ( Order_Items[Gross Profit] ), {REV} )", R0, "Net Sales minus COGS for revenue orders.")
add(S, "Gross Margin %", "DIVIDE ( [Gross Profit], [Net Sales] )", PCT, "Gross Profit / Net Sales.")
add(S, "Discount Amount", "[Gross Sales (List Price)] - [Net Sales]", R0, "Value given away through item and order discounts.")
add(S, "Discount Rate %", "DIVIDE ( [Discount Amount], [Gross Sales (List Price)] )", PCT, "Discount Amount / Gross Sales at list price.")
add(S, "Units Sold", f"CALCULATE ( SUM ( Order_Items[Quantity] ), {REV} )", INT, "Units on revenue orders.")
add(S, "Total Orders", "DISTINCTCOUNTNOBLANK ( Order_Items[Order ID] )", INT, "Orders placed, any status.")
add(S, "Revenue Orders", f"CALCULATE ( DISTINCTCOUNT ( Order_Items[Order ID] ), {REV} )", INT, "Orders that are not cancelled or returned.")
add(S, "Avg Order Value", "DIVIDE ( [Net Sales], [Revenue Orders] )", R0, "Net Sales per revenue order.")
add(S, "Profit per Order", "DIVIDE ( [Gross Profit], [Revenue Orders] )", R0, "Gross Profit per revenue order.")
add(S, "Lost Net Sales", f"CALCULATE ( SUM ( Order_Items[Net Sales] ), {NOREV} )", R0, "Net Sales on cancelled or returned orders.")
add(S, "Lost Gross Profit", f"CALCULATE ( SUM ( Order_Items[Gross Profit] ), {NOREV} )", R0, "Gross Profit forgone on cancelled or returned orders.")
add(S, "Cancel & Return Rate %", f"DIVIDE ( CALCULATE ( DISTINCTCOUNT ( Order_Items[Order ID] ), {NOREV} ), [Total Orders] )", PCT,
    "Share of placed orders that were cancelled or returned.")
add(S, "Loss-Making Lines", f"CALCULATE ( COUNTROWS ( Order_Items ), {REV}, Order_Items[Gross Profit] < 0 )", INT,
    "Order lines sold below cost after discounts.")
add(S, "Profit Lost on Loss-Making Lines", f"CALCULATE ( SUM ( Order_Items[Gross Profit] ), {REV}, Order_Items[Gross Profit] < 0 )", R0,
    "Total negative profit on lines sold below cost.")
add(S, "Gross Profit PY", PY("[Gross Profit]"), R0, "Gross Profit for the same period last year.")
add(S, "Gross Profit YoY %", "IF ( HASONEVALUE ( 'Date'[Year] ), DIVIDE ( [Gross Profit] - [Gross Profit PY], [Gross Profit PY] ) )", PCT,
    "Year-over-year change in Gross Profit (one year selected).")
add(S, "Net Sales PY", PY("[Net Sales]"), R0, "Net Sales for the same period last year.")
add(S, "Gross Margin % PY", PY("[Gross Margin %]"), PCT, "Gross margin for the same period last year.")
add(S, "Discount Rate % PY", PY("[Discount Rate %]"), PCT, "Discount rate for the same period last year.")
add(S, "Gross Profit 2024", "CALCULATE ( [Gross Profit], REMOVEFILTERS ( 'Date' ), 'Date'[Year] = 2024 )", R0,
    "Gross profit in 2024, the last full year (benchmark for the 2026 forecast).")

C2 = "2 Category"
ALLCAT = "REMOVEFILTERS ( Products )"
add(C2, "Category Profit Share %", f"DIVIDE ( [Gross Profit], CALCULATE ( [Gross Profit], {ALLCAT} ) )", PCT,
    "Gross Profit as a share of all products (keeps year and segment filters).")
add(C2, "Category Profit Rank", "IF ( NOT ISBLANK ( [Gross Profit] ), RANKX ( ALLSELECTED ( Products[Category] ), [Gross Profit], , DESC, DENSE ) )", "0",
    "Rank of the category by Gross Profit.")
add(C2, "Margin vs Avg (pp)", f"VAR m = [Gross Margin %] VAR avgm = CALCULATE ( [Gross Margin %], {ALLCAT} ) RETURN IF ( NOT ISBLANK ( m ), ( m - avgm ) * 100 )",
    "+0.0;-0.0;0.0", "Margin minus the margin of all products, in percentage points.")
add(C2, "Top Profit Category", 'CONCATENATEX ( TOPN ( 1, ALLSELECTED ( Products[Category] ), [Gross Profit], DESC ), Products[Category], ", " )', None,
    "Category with the highest Gross Profit.")
add(C2, "Lowest Profit Category",
    'CONCATENATEX ( TOPN ( 1, FILTER ( ALLSELECTED ( Products[Category] ), NOT ISBLANK ( [Gross Profit] ) ), [Gross Profit], ASC ), Products[Category], ", " )',
    None, "Category with the lowest Gross Profit.")
add(C2, "Top Subcategory", 'CONCATENATEX ( TOPN ( 1, FILTER ( VALUES ( Products[Subcategory] ), NOT ISBLANK ( [Gross Profit] ) ), [Gross Profit], DESC ), Products[Subcategory], ", " )',
    None, "Subcategory with the highest Gross Profit in the current selection.")
add(C2, "Selected Category", 'SELECTEDVALUE ( Products[Category], "All categories" )', None, "Category in the current filter context (drill-through title).")

C3 = "3 Customers"
add(C3, "Registered Customers", "COUNTROWS ( Customers )", INT, "All customers in the customer master.")
add(C3, "Purchasing Customers", 'CALCULATE ( COUNTROWS ( Customers ), Customers[Customer Type] <> "No Purchase" )', INT,
    "Customers who have placed at least one order.")
add(C3, "One-Time Customers", 'CALCULATE ( COUNTROWS ( Customers ), Customers[Customer Type] = "One-Time" )', INT,
    "Customers with exactly one lifetime order.")
add(C3, "Recurring Customers", 'CALCULATE ( COUNTROWS ( Customers ), Customers[Customer Type] = "Recurring" )', INT,
    "Customers with two or more lifetime orders.")
add(C3, "Recurring Customer %", "DIVIDE ( [Recurring Customers], [Purchasing Customers] )", PCT, "Repeat rate: recurring customers / buying customers.")
add(C3, "One-Time Customer %", "DIVIDE ( [One-Time Customers], [Purchasing Customers] )", PCT, "One-time customers / buying customers.")
add(C3, "Never-Purchased Customers", 'CALCULATE ( COUNTROWS ( Customers ), Customers[Customer Type] = "No Purchase" )', INT,
    "Registered customers with no order ever.")
add(C3, "Customer Activation Rate %", "DIVIDE ( [Purchasing Customers], [Registered Customers] )", PCT,
    "Share of registered customers who have placed at least one order.")
add(C3, "Avg Orders per Customer", "DIVIDE ( [Total Orders], [Purchasing Customers] )", D2, "Lifetime orders (any status) per buying customer.")
add(C3, "Buyers With 3+ Orders %", "DIVIDE ( CALCULATE ( [Purchasing Customers], Customers[Lifetime Orders] >= 3 ), [Purchasing Customers] )", PCT,
    "Share of buying customers with three or more lifetime orders.")
add(C3, "Recurring Customer Profit", 'CALCULATE ( [Gross Profit], Customers[Customer Type] = "Recurring" )', R0,
    "Gross Profit from customers with 2+ lifetime orders.")
add(C3, "One-Time Customer Profit", 'CALCULATE ( [Gross Profit], Customers[Customer Type] = "One-Time" )', R0,
    "Gross Profit from customers with exactly one lifetime order.")
add(C3, "Recurring Profit Share %", "DIVIDE ( [Recurring Customer Profit], [Gross Profit] )", PCT, "Share of Gross Profit generated by recurring customers.")
add(C3, "Profit per Recurring Customer", 'DIVIDE ( [Recurring Customer Profit], CALCULATE ( [Active Customers], Customers[Customer Type] = "Recurring" ) )', R0,
    "Gross Profit per recurring customer.")
add(C3, "Profit per One-Time Customer", 'DIVIDE ( [One-Time Customer Profit], CALCULATE ( [Active Customers], Customers[Customer Type] = "One-Time" ) )', R0,
    "Gross Profit per one-time customer.")
add(C3, "Recurring Value Multiplier", "DIVIDE ( [Profit per Recurring Customer], [Profit per One-Time Customer] )", '0.0"x"',
    "How many times more profit a recurring customer brings than a one-time customer.")
add(C3, "New Buyers", "CALCULATE ( COUNTROWS ( Customers ), TREATAS ( VALUES ( 'Date'[Date] ), Customers[First Order Date] ) )", INT,
    "Customers whose first order falls in the period.")
add(C3, "New Buyers 2024", "CALCULATE ( [New Buyers], REMOVEFILTERS ( 'Date' ), 'Date'[Year] = 2024 )", INT, "New buyers in 2024, the last full year.")
add(C3, "Last Sign-up Date", "MAX ( Customers[Join Date] )", "dd mmm yyyy", "Most recent registration date in the selection.")

K = "4 KPI"
add(K, "Active Customers", f"CALCULATE ( DISTINCTCOUNT ( Order_Items[Customer ID] ), {REV} )", INT,
    "Customers with at least one revenue order in the period.")
add(K, "Orders per Active Customer", "DIVIDE ( [Revenue Orders], [Active Customers] )", D2, "Purchase frequency: revenue orders per active customer.")
add(K, "Profit per Active Customer", "DIVIDE ( [Gross Profit], [Active Customers] )", R0,
    "HEADLINE KPI (PPAC). Gross Profit per active customer = Orders per Customer x Avg Order Value x Gross Margin %.")
add(K, "Profit per Active Customer PY", PY("[Profit per Active Customer]"), R0, "PPAC for the same period last year.")
add(K, "KPI Target Growth %", "0.05", PCT, "Assumed growth target over last year. Edit this value to change the target.")
add(K, "Profit per Active Customer Target", "[Profit per Active Customer PY] * ( 1 + [KPI Target Growth %] )", R0, "Last year's PPAC plus the target growth.")
add(K, "Profit per Active Customer YoY %",
    "IF ( HASONEVALUE ( 'Date'[Year] ), DIVIDE ( [Profit per Active Customer] - [Profit per Active Customer PY], [Profit per Active Customer PY] ) )", PCT,
    "Year-over-year change in PPAC (one year selected).")
add(K, "KPI vs Target %", "DIVIDE ( [Profit per Active Customer] - [Profit per Active Customer Target], [Profit per Active Customer Target] )", PCT,
    "PPAC versus target.")
add(K, "KPI Status", "VAR v = [Profit per Active Customer] VAR t = [Profit per Active Customer Target] RETURN SWITCH ( TRUE (), "
    "NOT HASONEVALUE ( 'Date'[Year] ), \"Pick a year\", ISBLANK ( t ), \"No target\", v >= t, \"On target\", v >= t * 0.95, \"Watch\", \"Below\" )",
    None, "Traffic-light status of PPAC: on target, watch (within 5%), below.")
add(K, "KPI Status Color", "VAR v = [Profit per Active Customer] VAR t = [Profit per Active Customer Target] RETURN SWITCH ( TRUE (), "
    f"ISBLANK ( t ), \"{NEUTRAL}\", v >= t, \"{GOOD}\", v >= t * 0.95, \"{WARN}\", \"{BAD}\" )", None,
    "Colour for the PPAC status: green on target, amber within 5%, red below (AA contrast).")
add(K, "Repeat Purchase Rate %",
    f"DIVIDE ( COUNTROWS ( FILTER ( VALUES ( Order_Items[Customer ID] ), CALCULATE ( DISTINCTCOUNT ( Order_Items[Order ID] ), {REV} ) >= 2 ) ), [Active Customers] )",
    PCT, "Share of active customers with 2+ revenue orders in the period.")
add(K, "Orders per Active Customer PY", PY("[Orders per Active Customer]"), D2, "Orders per active customer, same period last year.")
add(K, "Avg Order Value PY", PY("[Avg Order Value]"), R0, "Average order value, same period last year.")
add(K, "Active Customers PY", PY("[Active Customers]"), INT, "Active customers, same period last year.")

# ---------------------------------------------------------------- 5 Forecast
F = "5 Forecast"
SC = 'VAR sc = SELECTEDVALUE ( Scenario[Scenario], "A · No new sign-ups" )'
MT = 'VAR mt = SELECTEDVALUE ( Forecast[Metric], "Gross profit" )'
_f = lambda c: f"CALCULATE ( SUM ( Forecast[{c}] ), TREATAS ( {{ sc }}, Scenario[Scenario] ), TREATAS ( {{ mt }}, Forecast[Metric] ) )"
UNIT = 'IF ( mt IN { "Gross profit", "Net sales" }, 100000, 1 )'   # chart in ₹ L, or counts


def fc(c):
    """Forecast series in chart units. P10/P50/P90 also take the last actual month, so the forecast joins the history line."""
    if c == "Actual":
        return f"{SC} {MT} RETURN DIVIDE ( {_f('Actual')}, {UNIT} )"
    last = (f"CALCULATE ( MAX ( Forecast[Month] ), REMOVEFILTERS ( Forecast[Month] ), NOT ISBLANK ( Forecast[Actual] ), "
            f"TREATAS ( {{ sc }}, Scenario[Scenario] ), TREATAS ( {{ mt }}, Forecast[Metric] ) )")
    return (f"{SC} {MT} VAR v = {_f(c)} VAR lastA = {last} "
            f"RETURN DIVIDE ( IF ( ISBLANK ( v ) && MAX ( Forecast[Month] ) = lastA, {_f('Actual')}, v ), {UNIT} )")


f26 = lambda metric, c="P50": (f"{SC} RETURN CALCULATE ( SUM ( 'Forecast 2026'[{c}] ), 'Forecast 2026'[Metric] = \"{metric}\", "
                               f"TREATAS ( {{ sc }}, Scenario[Scenario] ) )")
add(F, "Fcst Actual", fc("Actual"), "#,##0.0", "History for the forecast chart: ₹ L for profit and sales, counts otherwise (defaults: scenario A, Gross profit).")
add(F, "Fcst P50", fc("P50"), "#,##0.0", "Forecast median, in chart units.")
add(F, "Fcst P10", fc("P10"), "#,##0.0", "Forecast low case (P10), in chart units.")
add(F, "Fcst P90", fc("P90"), "#,##0.0", "Forecast high case (P90), in chart units.")
add(F, "F26 Gross Profit", f26("Gross profit"), R0, "2026 gross profit, simulation median.")
add(F, "F26 Gross Profit Low", f26("Gross profit", "P10"), R0, "2026 gross profit, low case (P10).")
add(F, "F26 Gross Profit High", f26("Gross profit", "P90"), R0, "2026 gross profit, high case (P90).")
add(F, "F26 Revenue Orders", f26("Revenue orders"), INT, "2026 revenue orders, median.")
add(F, "F26 New Buyers", f26("New buyers"), INT, "2026 first-time buyers, median.")
add(F, "F26 PPAC", f26("PPAC"), R0, "2026 profit per active customer, median.")
add(F, "F26 PPAC Target", f26("PPAC target"), R0, "2026 PPAC target (2025 run-rate + 5%).")
add(F, "F26 P(PPAC hits target)", f26("P(PPAC hits target)"), "0%", "Share of simulated runs in which 2026 PPAC reaches its target.")
add(F, "Lever Uplift", "SUM ( Levers[Uplift Mid] )", R0, "Mid estimate of extra 2026 gross profit.")
add(F, "Lever Uplift Low", "SUM ( Levers[Uplift Low] )", R0, "Low estimate of extra 2026 gross profit.")
add(F, "Lever Uplift High", "SUM ( Levers[Uplift High] )", R0, "High estimate of extra 2026 gross profit.")
add(F, "Lever Uplift ₹ L", "DIVIDE ( [Lever Uplift], 100000 )", LAKH, "Mid lever uplift in lakh, for the lever chart.")
add(F, "Lever Uplift Low ₹ L", "DIVIDE ( [Lever Uplift Low], 100000 )", LAKH, "Low lever uplift in lakh (tooltip).")
add(F, "Lever Uplift High ₹ L", "DIVIDE ( [Lever Uplift High], 100000 )", LAKH, "High lever uplift in lakh (tooltip).")

# ---------------------------------------------------------------- 6 Display: chart units, card text, change lines, footer
D = "6 Display"


def card(name, expr, desc):
    add(D, f"Card {name}", expr, None, desc)


def delta(name, cur, py, pp=False, good_up=True, label="vs last year"):
    """Text + colour measures for a card's change line, e.g. '▲ 6.1% vs last year'."""
    d = f"( {cur} - {py} ) * 100" if pp else f"DIVIDE ( {cur} - {py}, {py} )"
    fmt = 'FORMAT ( ABS ( d ), "0.0" ) & " pp"' if pp else 'FORMAT ( ABS ( d ), "0.0%" )'
    add(D, f"Δ {name}", f"VAR p = {py} VAR d = {d} RETURN IF ( NOT HASONEVALUE ( 'Date'[Year] ), \"{PERIOD}\", "
        f"IF ( ISBLANK ( p ), \"No prior year\", IF ( d >= 0, \"{UP}\", \"{DOWN}\" ) & {fmt} & \" {label}\" ) )", None,
        f"Card change line for {name}: arrow and change {label}.")
    good, bad = (GOOD, BAD) if good_up else (BAD, GOOD)
    add(D, f"Δ {name} Color", f"VAR p = {py} RETURN IF ( NOT HASONEVALUE ( 'Date'[Year] ) || ISBLANK ( p ), \"{NEUTRAL}\", "
        f"IF ( {cur} >= p, \"{good}\", \"{bad}\" ) )", None,
        f"Colour of the {name} change line: {'green up, red down' if good_up else 'red up, green down'}, grey when not comparable.")


def ctx(name, expr, desc):
    add(D, f"Δ {name}", expr, None, desc)


add(D, "Gross Profit ₹ L", "DIVIDE ( [Gross Profit], 100000 )", LAKH, "Gross profit in lakh (₹1 L = ₹1,00,000), for charts and tables.")
add(D, "Net Sales ₹ L", "DIVIDE ( [Net Sales], 100000 )", LAKH, "Net sales in lakh, for tables.")
add(D, "COGS ₹ L", "DIVIDE ( [COGS], 100000 )", LAKH, "COGS in lakh, for tables.")
add(D, "Profit per Customer ₹ L", "DIVIDE ( [Profit per Active Customer], 100000 )", LAKH2, "Gross profit per active customer, in lakh.")
card("Gross Profit", inr("[Gross Profit]"), "Gross profit for cards, in Indian units (₹ L / ₹ Cr).")
card("Net Sales", inr("[Net Sales]"), "Net sales for cards, in Indian units.")
card("Gross Margin", 'FORMAT ( [Gross Margin %], "0.0%" )', "Gross margin for cards.")
card("Discount Rate", 'FORMAT ( [Discount Rate %], "0.0%" )', "Discount rate for cards.")
card("PPAC", inr("[Profit per Active Customer]"), "PPAC for cards.")
card("PPAC Target", inr("[Profit per Active Customer Target]"), "PPAC target for cards.")
card("AOV", inr("[Avg Order Value]"), "Average order value for cards.")
card("Orders per Customer", 'FORMAT ( [Orders per Active Customer], "0.00" )', "Orders per active customer for cards.")
card("Active Customers", 'FORMAT ( [Active Customers], "#,##0", "en-US" )', "Active customers for cards.")
card("Buyers", 'FORMAT ( [Purchasing Customers], "#,##0", "en-US" )', "Buying customers for cards.")
card("Repeat Rate", 'FORMAT ( [Recurring Customer %], "0.0%" )', "Repeat rate for cards.")
card("Recurring Profit Share", 'FORMAT ( [Recurring Profit Share %], "0.0%" )', "Recurring customers' share of gross profit, for cards.")
card("Value Multiplier", 'FORMAT ( [Recurring Value Multiplier], "0.0" ) & "x"', "Recurring vs one-time profit per customer, for cards.")
card("Avg Orders", 'FORMAT ( [Avg Orders per Customer], "0.00" )', "Lifetime orders per buying customer, for cards.")
card("Never Ordered", 'FORMAT ( [Never-Purchased Customers], "#,##0" )', "Registered customers who never ordered, for cards.")
card("Profit per Recurring", inr("[Profit per Recurring Customer]"), "Profit per recurring customer, in Indian units.")
card("Profit per One-Time", inr("[Profit per One-Time Customer]"), "Profit per one-time customer, in Indian units.")
card("Recurring Profit", inr("[Recurring Customer Profit]"), "Gross profit from recurring customers, in Indian units.")
card("Category Share", 'FORMAT ( [Category Profit Share %], "0%" )', "Share of all gross profit, for cards.")
card("Loss Lines", 'IF ( ISBLANK ( [Loss-Making Lines] ), "0", FORMAT ( [Loss-Making Lines], "#,##0" ) )', "Lines sold below cost, for cards.")
card("F26 Gross Profit", f'FORMAT ( DIVIDE ( [F26 Gross Profit], 100000 ), "{RUPEE}#,##0.0", "en-US" ) & " L"', "2026 gross profit forecast in lakh, for cards (same unit as its range).")
card("F26 Range", f'"{RUPEE}" & FORMAT ( DIVIDE ( [F26 Gross Profit Low], 100000 ), "0" ) & "–" & FORMAT ( DIVIDE ( [F26 Gross Profit High], 100000 ), "0" ) & " L"',
     "80% range of 2026 gross profit, in lakh.")
card("F26 Orders", 'FORMAT ( [F26 Revenue Orders], "#,##0" )', "2026 revenue orders forecast, for cards.")
card("F26 New Buyers", 'FORMAT ( [F26 New Buyers], "#,##0" )', "2026 new buyers forecast, for cards.")
card("F26 PPAC", inr("[F26 PPAC]"), "2026 PPAC forecast, for cards.")
card("F26 Hit Chance", 'FORMAT ( [F26 P(PPAC hits target)], "0%" )', "Chance that 2026 PPAC reaches its target, for cards.")
ctx("Buyers", '"of " & FORMAT ( [Registered Customers], "#,##0" ) & " registered (" & FORMAT ( [Customer Activation Rate %], "0%" ) & ")"',
    "Card line: buyers out of registered customers.")
ctx("Repeat Rate", 'FORMAT ( [Recurring Customers], "#,##0" ) & " vs " & FORMAT ( [One-Time Customers], "#,##0" ) & " one-time"',
    "Card line: recurring and one-time customer counts.")
ctx("Recurring Profit Share", '[Card Recurring Profit] & " of " & [Card Gross Profit]', "Card line: recurring profit out of the total.")
ctx("Value Multiplier", f'{lakh2("[Profit per Recurring Customer]")} & " vs " & {lakh2("[Profit per One-Time Customer]")}', "Card line: profit per customer by type.")
ctx("Avg Orders", 'FORMAT ( [Buyers With 3+ Orders %], "0%" ) & " ordered 3+ times"', "Card line: share of buyers with 3+ orders.")
ctx("Never Ordered", 'FORMAT ( DIVIDE ( [Never-Purchased Customers], [Registered Customers] ), "0%" ) & " of registered"',
    "Card line: never-ordered customers as a share of registered.")
delta("Gross Profit", "[Gross Profit]", "[Gross Profit PY]")
delta("Net Sales", "[Net Sales]", "[Net Sales PY]")
delta("Gross Margin", "[Gross Margin %]", "[Gross Margin % PY]", pp=True)
delta("Discount Rate", "[Discount Rate %]", "[Discount Rate % PY]", pp=True, good_up=False)
delta("PPAC", "[Profit per Active Customer]", "[Profit per Active Customer PY]")
delta("Orders per Customer", "[Orders per Active Customer]", "[Orders per Active Customer PY]")
delta("AOV", "[Avg Order Value]", "[Avg Order Value PY]")
delta("Active Customers", "[Active Customers]", "[Active Customers PY]")
for which, m_ in (("Top", "[Top Profit Category]"), ("Lowest", "[Lowest Profit Category]")):
    ctx(f"{which} Category", f"VAR c = {m_} VAR gp = CALCULATE ( [Gross Profit], Products[Category] = c ) "
        f'RETURN {inr("gp", "g")} & " · " & FORMAT ( DIVIDE ( gp, [Gross Profit] ), "0%" ) & " of profit"',
        f"Card line: gross profit and share of the {which.lower()} category.")
ctx("PPAC Target", "VAR v = [Profit per Active Customer] VAR t = [Profit per Active Customer Target] RETURN IF ( ISBLANK ( t ), \"No target (first year)\", "
    "FORMAT ( ABS ( DIVIDE ( v - t, t ) ), \"0.0%\" ) & IF ( v >= t, \" ahead of target\", \" behind target\" ) )",
    "Card line: PPAC distance from target (coloured by KPI Status Color).")
ctx("Category Margin", 'FORMAT ( [Margin vs Avg (pp)], "+0.0;-0.0;0.0" ) & " pp vs all products"', "Card line: margin gap to all products.")
ctx("Category Share", '"of " & ' + inr("CALCULATE ( [Gross Profit], REMOVEFILTERS ( Products ) )", "t") + ' & " total"', "Card line: total gross profit.")
ctx("Loss Lines", f'{inr("-[Profit Lost on Loss-Making Lines]", "l")} & " lost below cost"', "Card line: profit lost on lines sold below cost.")
ctx("F26 Gross Profit", f"VAR b = [Gross Profit 2024] VAR d = DIVIDE ( [F26 Gross Profit] - b, b ) RETURN IF ( d >= 0, \"{UP}\", \"{DOWN}\" ) & "
    f'FORMAT ( ABS ( d ), "0%" ) & " vs 2024 (" & {inr("b", "b")} & ")"', "Card line: 2026 forecast vs 2024 actual gross profit.")
add(D, "Δ F26 Gross Profit Color", f'IF ( [F26 Gross Profit] >= [Gross Profit 2024], "{GOOD}", "{BAD}" )', None, "Colour of the 2026 profit line.")
ctx("F26 Range", '"80% of 2,000 runs"', "Card line for the forecast range.")
ctx("F26 Orders", f"VAR b = CALCULATE ( [Revenue Orders], REMOVEFILTERS ( 'Date' ), 'Date'[Year] = 2024 ) VAR d = DIVIDE ( [F26 Revenue Orders] - b, b ) "
    f'RETURN IF ( d >= 0, "{UP}", "{DOWN}" ) & FORMAT ( ABS ( d ), "0%" ) & " vs 2024 (" & b & ")"', "Card line: 2026 orders vs 2024.")
add(D, "Δ F26 Orders Color", f"IF ( [F26 Revenue Orders] >= CALCULATE ( [Revenue Orders], REMOVEFILTERS ( 'Date' ), 'Date'[Year] = 2024 ), \"{GOOD}\", \"{BAD}\" )",
    None, "Colour of the 2026 orders line.")
ctx("F26 New Buyers", f"VAR b = [New Buyers 2024] VAR d = DIVIDE ( [F26 New Buyers] - b, b ) "
    f'RETURN IF ( d >= 0, "{UP}", "{DOWN}" ) & FORMAT ( ABS ( d ), "0%" ) & " vs 2024 (" & b & ")"', "Card line: 2026 new buyers vs 2024.")
add(D, "Δ F26 New Buyers Color", f'IF ( [F26 New Buyers] >= [New Buyers 2024], "{GOOD}", "{BAD}" )', None, "Colour of the 2026 new-buyer line.")
ctx("F26 PPAC", f"VAR t = [F26 PPAC Target] VAR d = DIVIDE ( [F26 PPAC] - t, t ) RETURN FORMAT ( ABS ( d ), \"0%\" ) & IF ( d >= 0, \" above \", \" below \" ) & "
    f'{inr("t", "t")} & " target"', "Card line: 2026 PPAC vs its target.")
add(D, "Δ F26 PPAC Color", f'IF ( [F26 PPAC] >= [F26 PPAC Target], "{GOOD}", "{BAD}" )', None, "Colour of the 2026 PPAC line.")
ctx("F26 Hit Chance", '"of runs reach target"', "Card line for the target probability.")
add(D, "Δ Neutral Color", f'"{NEUTRAL}"', None, "Grey for card lines that carry context, not a change.")
add(D, "Δ Warn Color", f'"{WARN}"', None, "Amber for card lines that flag an opportunity or risk.")
add(D, "Footer Text", f'"Source: Online Sales Data, {PERIOD}  ·  Refreshed " & FORMAT ( MAX ( \'Refresh Info\'[Refreshed] ), "d mmm yyyy" ) & '
    '"  ·  Profit excl. shipping and marketing  ·  Synthetic-looking data"', None,
    "Footer: source, refresh date and the main caveats.")

# ---------------------------------------------------------------- 7 Titles: action titles that follow the slicers
TT = "7 Titles"
pct0 = lambda x: f'FORMAT ( {x}, "0%" )'
LASTYR = "CALCULATE ( MAX ( 'Date'[Year] ), REMOVEFILTERS ( 'Date' ) )"
YTD = "IF ( yr = YEAR ( CALCULATE ( MAX ( 'Date'[Date] ), REMOVEFILTERS ( 'Date' ) ) ) && MONTH ( CALCULATE ( MAX ( 'Date'[Date] ), REMOVEFILTERS ( 'Date' ) ) ) < 12, \" YTD\", \"\" )"
CATS = "ALLSELECTED ( Products[Category] )"
TITLES = [
    ("Title Retention",
     f'{pct0("[Recurring Customer %]")} & " of buyers came back, and they earn " & {pct0("[Recurring Profit Share %]")} & " of gross profit"',
     "Page 1 headline: repeat rate and recurring customers' share of gross profit."),
    ("Title New Buyers",
     "VAR seq = CONCATENATEX ( FILTER ( VALUES ( 'Date'[Year] ), NOT ISBLANK ( [New Buyers] ) ), [New Buyers], \"→\", 'Date'[Year], ASC ) "
     "RETURN \"Sign-ups stopped \" & FORMAT ( [Last Sign-up Date], \"d mmm yyyy\" ) & \"; new buyers \" & seq",
     "New-buyer chart title: last registration date and first-time buyers per year."),
    ("Title Order Frequency",
     f'{pct0("[One-Time Customer %]")} & " of buyers ordered once; " & {pct0("[Buyers With 3+ Orders %]")} & " ordered 3+ times"',
     "Order-frequency chart title."),
    ("Title Value per Customer",
     f'"Recurring buyers earn " & FORMAT ( [Recurring Value Multiplier], "0.0" ) & "x (" & {lakh2("[Profit per Recurring Customer]")} & " vs " & {lakh2("[Profit per One-Time Customer]")} & " each)"',
     "Profit-per-customer chart title."),
    ("Title Profit by Type",
     "VAR ys = FILTER ( VALUES ( 'Date'[Year] ), NOT ISBLANK ( [Gross Profit] ) ) VAR y0 = MINX ( ys, 'Date'[Year] ) VAR y1 = MAXX ( ys, 'Date'[Year] ) "
     "RETURN \"Repeat customers: \" & FORMAT ( CALCULATE ( [Recurring Profit Share %], 'Date'[Year] = y0 ), \"0%\" ) & \" of profit in \" & y0 "
     "& \", \" & FORMAT ( CALCULATE ( [Recurring Profit Share %], 'Date'[Year] = y1 ), \"0%\" ) & \" in \" & y1",
     "Profit-by-type chart title: recurring share of gross profit in the first and last year."),
    ("Title Segment",
     "VAR t = ADDCOLUMNS ( FILTER ( VALUES ( Customers[Segment] ), NOT ISBLANK ( [Purchasing Customers] ) ), \"@r\", [Recurring Customer %] ) "
     "VAR hi = MAXX ( TOPN ( 1, t, [@r], DESC ), Customers[Segment] ) VAR lo = MAXX ( TOPN ( 1, t, [@r], ASC ), Customers[Segment] ) "
     "RETURN IF ( COUNTROWS ( t ) = 1, \"Repeat rate in \" & hi & \": \" & FORMAT ( MAXX ( t, [@r] ), \"0%\" ), "
     "\"Repeat rate: \" & FORMAT ( MAXX ( t, [@r] ), \"0%\" ) & \" in \" & hi & \" vs \" & FORMAT ( MINX ( t, [@r] ), \"0%\" ) & \" in \" & lo )",
     "Segment chart title: highest and lowest repeat rate by segment."),
    ("Title Category",
     f"VAR tc = [Top Profit Category] VAR gp = CALCULATE ( [Gross Profit], Products[Category] = tc ) "
     f"VAR mm = ADDCOLUMNS ( {CATS}, \"@m\", [Gross Margin %] ) "
     f'RETURN tc & " leads with " & {inr("gp", "g")} & " (" & FORMAT ( DIVIDE ( gp, [Gross Profit] ), "0%" ) & " of profit); margins run " & '
     f'FORMAT ( MINX ( mm, [@m] ), "0%" ) & "–" & FORMAT ( MAXX ( mm, [@m] ), "0%" )',
     "Page 2 headline: top category, its profit and share, and the margin range."),
    ("Title GP by Category",
     f"VAR lo = [Lowest Profit Category] RETURN [Top Profit Category] & \" earns most; \" & lo & \" least (\" & "
     f'{inr("CALCULATE ( [Gross Profit], Products[Category] = lo )", "l")} & ")"',
     "Gross-profit-by-category chart title."),
    ("Title Margin by Category",
     f"VAR mm = ADDCOLUMNS ( {CATS}, \"@m\", [Gross Margin %] ) VAR hi = MAXX ( TOPN ( 1, mm, [@m], DESC ), Products[Category] ) "
     "VAR lo = MAXX ( TOPN ( 1, mm, [@m], ASC ), Products[Category] ) "
     "RETURN \"Margin is highest in \" & hi & \" (\" & FORMAT ( MAXX ( mm, [@m] ), \"0.0%\" ) & \") and thinnest in \" & lo & \" (\" & FORMAT ( MINX ( mm, [@m] ), \"0.0%\" ) & \")\"",
     "Margin-by-category chart title."),
    ("Title Discount",
     "VAR b = FILTER ( VALUES ( Order_Items[Item Discount %] ), NOT ISBLANK ( [Net Sales] ) ) VAR b0 = MINX ( b, Order_Items[Item Discount %] ) "
     "VAR b1 = MAXX ( b, Order_Items[Item Discount %] ) VAR m0 = CALCULATE ( [Gross Margin %], Order_Items[Item Discount %] = b0 ) "
     "VAR m1 = CALCULATE ( [Gross Margin %], Order_Items[Item Discount %] = b1 ) "
     "RETURN \"Margin \" & IF ( m1 < m0, \"falls\", \"rises\" ) & \" from \" & FORMAT ( m0, \"0%\" ) & \" at \" & b0 & \"% item discount to \" & FORMAT ( m1, \"0%\" ) & \" at \" & b1 & \"%\"",
     "Discount chart title: margin at the lowest and highest item discount."),
    ("Title Subcategory",
     f'VAR ts = [Top Subcategory] RETURN "Top subcategory: " & ts & " (" & {inr("CALCULATE ( [Gross Profit], Products[Subcategory] = ts )", "s")} & " gross profit)"',
     "Category P&L table title."),
    ("Title KPI",
     f"VAR yr = {LASTYR} VAR v = CALCULATE ( [Profit per Active Customer], 'Date'[Year] = yr ) "
     "VAR yoy = CALCULATE ( [Profit per Active Customer YoY %], 'Date'[Year] = yr ) VAR vt = CALCULATE ( [KPI vs Target %], 'Date'[Year] = yr ) "
     f'RETURN "PPAC is " & {inr("v", "p")} & " in " & yr & {YTD} & ": " & FORMAT ( ABS ( yoy ), "0.0%" ) & IF ( yoy >= 0, " above", " below" ) & " last year and " '
     '& FORMAT ( ABS ( vt ), "0.0%" ) & IF ( vt >= 0, " above", " below" ) & " target"',
     "Page 3 headline: PPAC in the latest year vs last year and target."),
    ("Title PPAC Quarter",
     "VAR q = FILTER ( VALUES ( 'Date'[Year Quarter] ), NOT ISBLANK ( [Profit per Active Customer Target] ) ) "
     "VAR hit = COUNTROWS ( FILTER ( q, [Profit per Active Customer] >= [Profit per Active Customer Target] ) ) "
     "RETURN \"PPAC met its target in \" & hit & \" of \" & COUNTROWS ( q ) & \" quarters that have a prior year\"",
     "Quarterly PPAC chart title: quarters on target."),
    ("Title Drivers",
     f"VAR yr = {LASTYR} "
     "VAR o = CALCULATE ( DIVIDE ( [Orders per Active Customer] - [Orders per Active Customer PY], [Orders per Active Customer PY] ), 'Date'[Year] = yr ) "
     "VAR a = CALCULATE ( DIVIDE ( [Avg Order Value] - [Avg Order Value PY], [Avg Order Value PY] ), 'Date'[Year] = yr ) "
     "VAR m = CALCULATE ( ( [Gross Margin %] - [Gross Margin % PY] ) * 100, 'Date'[Year] = yr ) "
     "RETURN \"In \" & yr & \", orders per customer \" & IF ( o >= 0, \"rose \", \"fell \" ) & FORMAT ( ABS ( o ), \"0.0%\" ) & \", order value \" & "
     "IF ( a >= 0, \"rose \", \"fell \" ) & FORMAT ( ABS ( a ), \"0.0%\" ) & \", margin \" & IF ( m >= 0, \"rose \", \"fell \" ) & FORMAT ( ABS ( m ), \"0.0\" ) & \" pp\"",
     "Driver table title: change in each PPAC driver, latest year vs the same months last year."),
    ("Title PPAC Segment",
     f"VAR yr = {LASTYR} VAR t = ADDCOLUMNS ( FILTER ( VALUES ( Customers[Segment] ), NOT ISBLANK ( CALCULATE ( [Active Customers], 'Date'[Year] = yr ) ) ), "
     "\"@p\", CALCULATE ( [Profit per Active Customer], 'Date'[Year] = yr ) ) "
     f'RETURN "PPAC in " & yr & {YTD} & ": " & CONCATENATEX ( t, Customers[Segment] & " " & {inr("[@p]", "p")}, " vs ", [@p], DESC )',
     "PPAC-by-segment chart title, latest year."),
    ("Title Forecast",
     f'"2026 gross profit: about " & [Card F26 Gross Profit] & " (80% range " & [Card F26 Range] & ") under scenario " & LEFT ( SELECTEDVALUE ( Scenario[Scenario], "A" ), 1 )',
     "Page 5 headline: 2026 gross profit forecast and its range for the selected scenario."),
    ("Title Levers",
     f'"Four levers, each worth {RUPEE}" & FORMAT ( DIVIDE ( MINX ( Levers, Levers[Uplift Low] ), 100000 ), "0.0" ) & "–" & FORMAT ( DIVIDE ( MAXX ( Levers, Levers[Uplift High] ), 100000 ), "0.0" ) & " L of 2026 gross profit"',
     "Lever chart title: range of the lever sizes."),
    ("Title Category Detail",
     f'[Selected Category] & ": " & [Card Gross Profit] & " gross profit (" & FORMAT ( [Category Profit Share %], "0%" ) & " of total), margin " & '
     'FORMAT ( [Gross Margin %], "0.0%" ) & "; top subcategory " & [Top Subcategory]',
     "Drill-through headline for one category."),
]
for n, e, d in TITLES:
    add(TT, n, e, None, d)

# ---------------------------------------------------------------- write _Measures
ms = f"/// Central home for report measures, in display folders 1-7.\ntable _Measures\n{T}{lt()}\n\n"
for n, e, f_, folder, desc in M:
    ms += f"{T}/// {desc}\n{T}measure {q(n) if not n.startswith(chr(39)) else n} = {e}\n"
    if f_: ms += f"{T * 2}formatString: {f_}\n"
    ms += f"{T * 2}displayFolder: {folder}\n{T * 2}{lt()}\n\n"
ms += column("Hidden", None, "", hidden=True, inferred=True)
ms += f"{T}partition _Measures = calculated\n{T * 2}mode: import\n{T * 2}source = ROW ( \"Hidden\", BLANK () )\n\n"
ms += f'{T}annotation BestPracticeAnalyzer_IgnoreRules = {{"RuleIDs":["ENSURE_TABLES_HAVE_RELATIONSHIPS","REMOVE_UNNECESSARY_COLUMNS"]}}\n'
w(DEFN / "tables" / "_Measures.tmdl", ms)

lv = (DEFN / "tables" / "Levers.tmdl").read_text(encoding="utf-8").rstrip("\n")
w(DEFN / "tables" / "Levers.tmdl", lv + f'\n\n{T}annotation BestPracticeAnalyzer_IgnoreRules = {{"RuleIDs":["ENSURE_TABLES_HAVE_RELATIONSHIPS"]}}\n')
folders = {}
for *_, folder, _ in M:
    folders[folder] = folders.get(folder, 0) + 1
print(f"model written: {len(M)} measures {folders}; tables {TABLES}")
