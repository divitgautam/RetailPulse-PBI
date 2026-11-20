import subprocess, sys, os

PBI = os.path.expanduser(r"~\.local\bin\pbi.exe")
T = "_Measures"
RUPEE = "₹#,##0"
PCT = "0.0%"
REV = "Order_Items[Is Revenue Order] = TRUE ()"

M = [
    # ---------- 1. Sales & Profit ----------
    ("Net Sales", f"CALCULATE ( SUM ( Order_Items[Net Sales] ), {REV} )", RUPEE, "1 Sales & Profit",
     "Revenue excluding tax and shipping, after item and order discounts. Excludes cancelled and returned orders."),
    ("Gross Sales (List Price)", f"CALCULATE ( SUM ( Order_Items[Gross Amount] ), {REV} )", RUPEE, "1 Sales & Profit",
     "Unit price x quantity before any discount. Excludes cancelled and returned orders."),
    ("COGS", f"CALCULATE ( SUM ( Order_Items[COGS] ), {REV} )", RUPEE, "1 Sales & Profit",
     "Product cost price x quantity for revenue orders."),
    ("Gross Profit", f"CALCULATE ( SUM ( Order_Items[Gross Profit] ), {REV} )", RUPEE, "1 Sales & Profit",
     "Net Sales minus COGS for revenue orders."),
    ("Gross Margin %", "DIVIDE ( [Gross Profit], [Net Sales] )", PCT, "1 Sales & Profit", "Gross Profit / Net Sales."),
    ("Discount Amount", "[Gross Sales (List Price)] - [Net Sales]", RUPEE, "1 Sales & Profit",
     "Value given away through item and order discounts."),
    ("Discount Rate %", "DIVIDE ( [Discount Amount], [Gross Sales (List Price)] )", PCT, "1 Sales & Profit",
     "Discount Amount / Gross Sales at list price."),
    ("Units Sold", f"CALCULATE ( SUM ( Order_Items[quantity] ), {REV} )", "#,##0", "1 Sales & Profit", "Units on revenue orders."),
    ("Revenue Orders", f"CALCULATE ( DISTINCTCOUNT ( Order_Items[order_id] ), {REV} )", "#,##0", "1 Sales & Profit",
     "Orders that are not cancelled or returned."),
    ("Avg Order Value", "DIVIDE ( [Net Sales], [Revenue Orders] )", RUPEE, "1 Sales & Profit", "Net Sales per revenue order."),
    ("Profit per Order", "DIVIDE ( [Gross Profit], [Revenue Orders] )", RUPEE, "1 Sales & Profit", "Gross Profit per revenue order."),
    ("Lost Net Sales", "CALCULATE ( SUM ( Order_Items[Net Sales] ), Order_Items[Is Revenue Order] = FALSE () )", RUPEE,
     "1 Sales & Profit", "Net Sales on cancelled or returned orders."),
    ("Lost Gross Profit", "CALCULATE ( SUM ( Order_Items[Gross Profit] ), Order_Items[Is Revenue Order] = FALSE () )", RUPEE,
     "1 Sales & Profit", "Gross Profit forgone on cancelled or returned orders."),
    ("Cancel & Return Rate %",
     "DIVIDE ( CALCULATE ( DISTINCTCOUNT ( Order_Items[order_id] ), Order_Items[Is Revenue Order] = FALSE () ), [Total Orders] )",
     PCT, "1 Sales & Profit", "Share of placed orders that were cancelled or returned."),
    ("Loss-Making Lines",
     f"COALESCE ( CALCULATE ( COUNTROWS ( Order_Items ), {REV}, Order_Items[Gross Profit] < 0 ), 0 )", "#,##0",
     "1 Sales & Profit", "Order lines sold below cost after discounts."),
    ("Profit Lost on Loss-Making Lines",
     f"CALCULATE ( SUM ( Order_Items[Gross Profit] ), {REV}, Order_Items[Gross Profit] < 0 )", RUPEE,
     "1 Sales & Profit", "Total negative profit on lines sold below cost."),
    ("Gross Profit PY", "CALCULATE ( [Gross Profit], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", RUPEE, "1 Sales & Profit",
     "Gross Profit for the same period last year."),
    ("Gross Profit YoY %", "DIVIDE ( [Gross Profit] - [Gross Profit PY], [Gross Profit PY] )", PCT, "1 Sales & Profit",
     "Year-over-year change in Gross Profit."),
    # ---------- 2. Category ----------
    ("Category Profit Share %", "DIVIDE ( [Gross Profit], CALCULATE ( [Gross Profit], ALLSELECTED ( Products[category] ) ) )", PCT,
     "2 Category", "Category Gross Profit as a share of the selected total."),
    ("Category Profit Rank", "IF ( NOT ISBLANK ( [Gross Profit] ), RANKX ( ALLSELECTED ( Products[category] ), [Gross Profit], , DESC, DENSE ) )",
     "0", "2 Category", "Rank of the category by Gross Profit."),
    ("Margin vs Avg (pp)",
     "VAR m = [Gross Margin %]\nVAR avgm = CALCULATE ( [Gross Margin %], ALLSELECTED ( Products[category] ) )\nRETURN IF ( NOT ISBLANK ( m ), ( m - avgm ) * 100 )",
     "+0.0;-0.0;0.0", "2 Category", "Category margin minus the overall margin, in percentage points."),
    ("Top Profit Category",
     "VAR t = TOPN ( 1, ALLSELECTED ( Products[category] ), [Gross Profit], DESC )\nRETURN CONCATENATEX ( t, Products[category], \", \" )",
     None, "2 Category", "Category with the highest Gross Profit."),
    ("Lowest Profit Category",
     "VAR t = TOPN ( 1, FILTER ( ALLSELECTED ( Products[category] ), NOT ISBLANK ( [Gross Profit] ) ), [Gross Profit], ASC )\nRETURN CONCATENATEX ( t, Products[category], \", \" )",
     None, "2 Category", "Category with the lowest Gross Profit."),
    # ---------- 3. Customers ----------
    ("Registered Customers", "COUNTROWS ( Customers )", "#,##0", "3 Customers", "All customers in the customer master."),
    ("Never-Purchased Customers", "COALESCE ( CALCULATE ( COUNTROWS ( Customers ), Customers[Lifetime Orders] = 0 ), 0 )", "#,##0",
     "3 Customers", "Registered customers with no order ever."),
    ("Customer Activation Rate %",
     "DIVIDE ( CALCULATE ( COUNTROWS ( Customers ), Customers[Lifetime Orders] > 0 ), [Registered Customers] )", PCT,
     "3 Customers", "Share of registered customers who have placed at least one order."),
    ("Avg Orders per Customer", "DIVIDE ( [Total Orders], [Purchasing Customers] )", "0.00", "3 Customers",
     "Orders placed per purchasing customer."),
    ("Recurring Customer Profit", "CALCULATE ( [Gross Profit], Customers[Customer Type] = \"Recurring\" )", RUPEE, "3 Customers",
     "Gross Profit from customers with 2+ lifetime orders."),
    ("One-Time Customer Profit", "CALCULATE ( [Gross Profit], Customers[Customer Type] = \"One-Time\" )", RUPEE, "3 Customers",
     "Gross Profit from customers with exactly one lifetime order."),
    ("Recurring Profit Share %", "DIVIDE ( [Recurring Customer Profit], [Gross Profit] )", PCT, "3 Customers",
     "Share of Gross Profit generated by recurring customers."),
    ("Profit per Recurring Customer",
     "DIVIDE ( [Recurring Customer Profit], CALCULATE ( [Active Customers], Customers[Customer Type] = \"Recurring\" ) )", RUPEE,
     "3 Customers", "Gross Profit per recurring customer."),
    ("Profit per One-Time Customer",
     "DIVIDE ( [One-Time Customer Profit], CALCULATE ( [Active Customers], Customers[Customer Type] = \"One-Time\" ) )", RUPEE,
     "3 Customers", "Gross Profit per one-time customer."),
    ("Recurring Value Multiplier", "DIVIDE ( [Profit per Recurring Customer], [Profit per One-Time Customer] )", "0.0\"x\"",
     "3 Customers", "How many times more profit a recurring customer brings than a one-time customer."),
    # ---------- 4. KPI ----------
    ("Active Customers", f"CALCULATE ( DISTINCTCOUNT ( Order_Items[customer_id] ), {REV} )", "#,##0", "4 KPI",
     "Customers with at least one revenue order in the period."),
    ("Orders per Active Customer", "DIVIDE ( [Revenue Orders], [Active Customers] )", "0.00", "4 KPI",
     "Purchase frequency: revenue orders per active customer."),
    ("Profit per Active Customer", "DIVIDE ( [Gross Profit], [Active Customers] )", RUPEE, "4 KPI",
     "HEADLINE KPI. Gross Profit per active customer = Orders per Customer x Avg Order Value x Gross Margin %."),
    ("Profit per Active Customer PY", "CALCULATE ( [Profit per Active Customer], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", RUPEE,
     "4 KPI", "Same KPI for the same period last year."),
    ("KPI Target Growth %", "0.05", PCT, "4 KPI", "Assumed growth target over last year. Edit this value to change the target."),
    ("Profit per Active Customer Target", "[Profit per Active Customer PY] * ( 1 + [KPI Target Growth %] )", RUPEE, "4 KPI",
     "Last year's value plus the target growth."),
    ("Profit per Active Customer YoY %",
     "DIVIDE ( [Profit per Active Customer] - [Profit per Active Customer PY], [Profit per Active Customer PY] )", PCT, "4 KPI",
     "Year-over-year change in the headline KPI."),
    ("KPI vs Target %",
     "DIVIDE ( [Profit per Active Customer] - [Profit per Active Customer Target], [Profit per Active Customer Target] )", PCT,
     "4 KPI", "Headline KPI versus target."),
    ("KPI Status",
     "VAR v = [Profit per Active Customer]\nVAR t = [Profit per Active Customer Target]\nRETURN SWITCH ( TRUE (), ISBLANK ( t ), \"No target (first year)\", v >= t, \"On target\", v >= t * 0.95, \"Watch: within 5% of target\", \"Below target\" )",
     None, "4 KPI", "Traffic-light status of the headline KPI."),
    ("KPI Status Color",
     "VAR v = [Profit per Active Customer]\nVAR t = [Profit per Active Customer Target]\nRETURN SWITCH ( TRUE (), ISBLANK ( t ), \"#8A8886\", v >= t, \"#107C10\", v >= t * 0.95, \"#C19C00\", \"#D13438\" )",
     None, "4 KPI", "Colour for the KPI status."),
    ("Repeat Purchase Rate %",
     "DIVIDE ( COUNTROWS ( FILTER ( VALUES ( Order_Items[customer_id] ), CALCULATE ( DISTINCTCOUNT ( Order_Items[order_id] ), Order_Items[Is Revenue Order] = TRUE () ) >= 2 ) ), [Active Customers] )",
     PCT, "4 KPI", "Share of active customers with 2+ revenue orders in the period."),
    ("Orders per Active Customer PY", "CALCULATE ( [Orders per Active Customer], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", "0.00", "4 KPI", ""),
    ("Avg Order Value PY", "CALCULATE ( [Avg Order Value], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", RUPEE, "4 KPI", ""),
    ("Gross Margin % PY", "CALCULATE ( [Gross Margin %], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", PCT, "4 KPI", ""),
    ("Active Customers PY", "CALCULATE ( [Active Customers], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", "#,##0", "4 KPI", ""),
]

only = set(sys.argv[1:])
for name, expr, fmt, folder, desc in M:
    if only and name not in only:
        continue
    args = [PBI, "measure", "create", name, "-e", "-", "-t", T, "--folder", folder]
    if fmt:
        args += ["--format-string", fmt]
    if desc:
        args += ["--description", desc]
    r = subprocess.run(args, input=expr, capture_output=True, text=True, encoding="utf-8")
    ok = "created" in (r.stdout + r.stderr)
    print(("OK   " if ok else "FAIL ") + name + ("" if ok else "\n" + (r.stdout + r.stderr)[-600:]))
