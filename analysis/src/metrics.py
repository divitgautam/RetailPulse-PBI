"""Shared loading, cleaning and metric definitions for the RetailPulse-PBI analysis.

Definitions match the Power BI model (RetailPulse-PBI.SemanticModel) exactly:
- Net sales  = unit_price x quantity x (1 - item_discount%) x (1 - order_discount%)   (excl. tax and shipping)
- COGS       = Products.cost_price x quantity
- Gross profit = net sales - COGS
- Revenue order = order_status not in {Cancelled, Returned}
- Customer duplicates: keep the row with the most non-null fields per customer_id; drop stub rows
  (no email, join_date or segment)
- Missing order_date on a line: filled from the other lines of the same order
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = PROJECT_DIR / "analysis"
DATA_DIR = ANALYSIS_DIR / "data"
OUTPUT_DIR = ANALYSIS_DIR / "output"

def _default_raw_path() -> Path:
    """INXITE_RAW_XLSX env var, else data/Online Sales Data.xlsx in the repo, else the original Downloads location."""
    if os.environ.get("INXITE_RAW_XLSX"):
        return Path(os.environ["INXITE_RAW_XLSX"])
    local = PROJECT_DIR / "data" / "Online Sales Data.xlsx"
    return local if local.exists() else Path.home() / "Downloads" / "Online Sales Data.xlsx"


RAW_PATH = _default_raw_path()
NON_REVENUE_STATUSES = {"Cancelled", "Returned"}
DATA_END = pd.Timestamp("2025-10-31")

# Totals shown in the Power BI report; Python must reproduce them.
PBI_TOTALS = {
    "net_sales": 108_222_683,
    "gross_profit": 28_643_394,
    "revenue_orders": 386,
    "purchasing_customers": 220,
    "customers_clean": 300,
}


def load_raw(path: Path | str = RAW_PATH) -> dict[str, pd.DataFrame]:
    """Read the three sheets exactly as they are in Excel."""
    sheets = pd.read_excel(path, sheet_name=["Customers", "Products", "Order_Items"])
    for df in sheets.values():
        df.columns = [c.strip() for c in df.columns]
    return sheets


def dedupe_customers(customers: pd.DataFrame) -> pd.DataFrame:
    """Drop blank IDs, then keep the most complete row per customer_id (same rule as Power Query)."""
    c = customers.copy()
    c["customer_id"] = c["customer_id"].astype("string").str.strip()
    c = c[c["customer_id"].notna() & (c["customer_id"] != "")]
    c["_filled"] = c.notna().sum(axis=1)
    c = (c.sort_values(["customer_id", "_filled"], ascending=[True, False], kind="stable")
           .drop_duplicates("customer_id", keep="first")
           .drop(columns="_filled"))
    # Drop stub rows that carry no identifying data (same rule as Power Query "Removed stub rows").
    stub = c["email"].isna() & c["join_date"].isna() & c["segment"].isna()
    return c[~stub].reset_index(drop=True)


def build_lines(order_items: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Line-level fact with net sales, COGS and gross profit."""
    li = order_items.merge(
        products[["product_id", "category", "subcategory", "cost_price", "unit_price"]]
        .rename(columns={"unit_price": "list_price"}),
        on="product_id", how="left", validate="many_to_one")
    # 23 cancelled lines have no order_date; every such order has its date on another line, so fill it from the order.
    li["order_date_imputed"] = li["order_date"].isna()
    li["order_date"] = li.groupby("order_id")["order_date"].transform("first")
    li["gross_amount"] = li["unit_price"] * li["quantity"]
    li["net_sales"] = (li["gross_amount"]
                       * (1 - li["item_discount_percent"] / 100)
                       * (1 - li["discount_percent"] / 100))
    li["cogs"] = li["cost_price"] * li["quantity"]
    li["gross_profit"] = li["net_sales"] - li["cogs"]
    li["is_revenue"] = ~li["order_status"].isin(NON_REVENUE_STATUSES)
    li["order_month"] = li["order_date"].dt.to_period("M").dt.to_timestamp()
    return li


def build_orders(lines: pd.DataFrame) -> pd.DataFrame:
    """One row per order. Order-level fields use first(); line amounts are summed."""
    g = lines.groupby("order_id", sort=True)
    orders = g.agg(
        order_date=("order_date", "first"),
        customer_id=("customer_id", "first"),
        order_status=("order_status", "first"),
        payment_method=("payment_method", "first"),
        discount_percent=("discount_percent", "first"),
        items_total=("items_total", "first"),
        total_amount=("total_amount", "first"),
        lines=("order_item_id", "count"),
        units=("quantity", "sum"),
        line_total_sum=("line_total", "sum"),
        gross_amount=("gross_amount", "sum"),
        net_sales=("net_sales", "sum"),
        cogs=("cogs", "sum"),
        gross_profit=("gross_profit", "sum"),
        is_revenue=("is_revenue", "first"),
    ).reset_index()
    orders["implied_shipping"] = (orders["total_amount"]
                                  - orders["items_total"] * (1 - orders["discount_percent"] / 100)).round(2)
    return orders


def build_customers(customers_clean: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """Customer dimension with lifetime behaviour (all placed orders count toward type, like Power BI)."""
    per = orders.groupby("customer_id").agg(
        lifetime_orders=("order_id", "nunique"),
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
    )
    rev = orders[orders["is_revenue"]].groupby("customer_id").agg(
        revenue_orders=("order_id", "nunique"),
        lifetime_net_sales=("net_sales", "sum"),
        lifetime_gross_profit=("gross_profit", "sum"),
    )
    c = customers_clean.merge(per, on="customer_id", how="left").merge(rev, on="customer_id", how="left")
    c["lifetime_orders"] = c["lifetime_orders"].fillna(0).astype(int)
    c["customer_type"] = np.select([c["lifetime_orders"].eq(0), c["lifetime_orders"].eq(1)],
                                   ["No Purchase", "One-Time"], default="Recurring")
    return c


def load_clean(path: Path | str = RAW_PATH) -> dict[str, pd.DataFrame]:
    raw = load_raw(path)
    customers = dedupe_customers(raw["Customers"])
    lines = build_lines(raw["Order_Items"], raw["Products"])
    orders = build_orders(lines)
    return {
        "raw": raw,
        "customers": build_customers(customers, orders),
        "products": raw["Products"].copy(),
        "lines": lines,
        "orders": orders,
    }


def reconcile(customers: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Compare Python totals with the Power BI report."""
    rev = lines[lines["is_revenue"]]
    py = {
        "net_sales": rev["net_sales"].sum(),
        "gross_profit": rev["gross_profit"].sum(),
        "revenue_orders": rev["order_id"].nunique(),
        "purchasing_customers": lines["customer_id"].nunique(),
        "customers_clean": len(customers),
    }
    out = pd.DataFrame({"python": py, "power_bi": PBI_TOTALS})
    out["diff"] = out["python"] - out["power_bi"]
    out["match"] = out["diff"].abs() < 1  # rupee rounding tolerance
    return out
