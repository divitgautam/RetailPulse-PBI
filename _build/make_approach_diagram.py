"""Draws docs/approach_diagram.png (1920x1080) in the InXiteOut palette. Run: python _build/make_approach_diagram.py"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap

OUT = Path(__file__).resolve().parents[1] / "docs"
OUT.mkdir(exist_ok=True)
NAVY, VIOLET, LILAC, PURPLE, WHITE, INK, MUTED = "#030734", "#682EFF", "#CD83FF", "#AC24FF", "#FFFFFF", "#020618", "#62748E"
plt.rcParams["font.family"] = "Segoe UI"

W, H = 19.2, 10.8
fig = plt.figure(figsize=(W, H), dpi=100)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

# background: navy to purple diagonal, like the site's hero bands
grad = LinearSegmentedColormap.from_list("bg", [NAVY, NAVY, "#2A0F6E", "#5B19B8"])
xx, yy = np.meshgrid(np.linspace(0, 1, 400), np.linspace(0, 1, 225))
ax.imshow(grad(np.clip(xx * .75 + (1 - yy) * .35 - .15, 0, 1)), extent=[0, W, 0, H], aspect="auto", zorder=0)

ax.text(.8, 9.95, "From raw sales data to profit decisions", color=WHITE, fontsize=34, weight="bold", va="top")
ax.text(.8, 9.1, "How the Inxite-Out analysis was built: audit first, model once, answer in Power BI, go deeper in Python",
        color="#C8C3F5", fontsize=15, va="top")

stages = [
    ("01", "DATA", "Online sales workbook",
     ["Customers: 307 rows", "Products: 200", "Order lines: 1,500", "405 orders, Jan 2023 to Oct 2025"]),
    ("02", "AUDIT & MODEL", "Trust before charts",
     ["20 data-quality checks", "Fixed: duplicate customers,", "many-to-many join, missing dates", "Avoided a 4.6x revenue overcount",
      "Star schema + Date table"]),
    ("03", "POWER BI", "Answer the brief",
     ["69 DAX measures, 14 columns", "5 pages, 55 visuals", "Retention | Category profit", "KPI: profit per active customer",
      "Forecast & profit levers"]),
    ("04", "PYTHON", "Go deeper",
     ["EDA: 18 questions", "Cohorts, survival curve, RFM", "Forecast: customer simulation,", "backtested on held-out months",
      "BG/NBD + scenario models"]),
    ("05", "DECISIONS", "What to do next",
     ["Plan ~Rs 1 Cr gross profit 2026", "Cap discounts: +Rs 12 L", "Activate 80 sign-ups: +Rs 16 L",
      "Investigate sign-up stop", "Same follow-up for all buyers"]),
]
n = len(stages); gap = .42; left = .8; cw = (W - 2 * left - (n - 1) * gap) / n; top, ch = 8.1, 5.15
for i, (num, name, tag, lines) in enumerate(stages):
    x = left + i * (cw + gap)
    hi = i in (2, 3)
    box = FancyBboxPatch((x, top - ch), cw, ch, boxstyle="round,pad=0,rounding_size=.22",
                         fc=WHITE, ec=LILAC if hi else "none", lw=2.5, zorder=2)
    ax.add_patch(box)
    ax.add_patch(FancyBboxPatch((x, top - .14), cw, .14, boxstyle="round,pad=0,rounding_size=.07",
                                fc=VIOLET if i % 2 == 0 else PURPLE, ec="none", zorder=3))
    ax.text(x + .32, top - .45, num, color=VIOLET, fontsize=30, weight="bold", va="top", zorder=4)
    ax.text(x + .32, top - 1.32, name, color=INK, fontsize=17, weight="bold", va="top", zorder=4)
    ax.text(x + .32, top - 1.82, tag, color=MUTED, fontsize=12.5, va="top", style="italic", zorder=4)
    for j, ln in enumerate(lines):
        ln = ln.replace("Rs ", "₹")
        ax.text(x + .32, top - 2.45 - j * .5, ln, color=INK, fontsize=12.5, va="top", zorder=4)
    if i < n - 1:
        ax.add_patch(FancyArrowPatch((x + cw + .04, top - ch / 2), (x + cw + gap - .04, top - ch / 2),
                                     arrowstyle="-|>,head_length=8,head_width=6", color=LILAC, lw=2.5, zorder=5))

# reconciliation band joining Power BI and Python
bx = left + 2 * (cw + gap); bw = 2 * cw + gap
ax.add_patch(FancyBboxPatch((bx, 1.6), bw, .93, boxstyle="round,pad=0,rounding_size=.18", fc=VIOLET, ec="none", zorder=2))
ax.text(bx + bw / 2, 2.25, "Reconciled to the rupee: Python = Power BI", color=WHITE, fontsize=14, weight="bold",
        ha="center", va="center", zorder=3)
ax.text(bx + bw / 2, 1.88, "₹10.8 Cr net sales  |  ₹2.86 Cr gross profit  |  386 revenue orders  |  220 buyers",
        color="#E9E2FF", fontsize=12, ha="center", va="center", zorder=3)
for cx in (bx + cw / 2, bx + cw + gap + cw / 2):
    ax.plot([cx, cx], [top - ch, 2.53], color=LILAC, lw=2, ls=(0, (3, 3)), zorder=1)

ax.text(.8, 1.0, "Key finding: buyers are steady but slow (median 254 days to a 2nd order); "
        "growth stalled because sign-ups stopped in Sep 2024, not because customers left.",
        color=WHITE, fontsize=14.5, va="center")
ax.text(W - .8, .45, "Power BI  |  DAX  |  Power Query  |  Python (pandas, statsmodels, scipy, scikit-learn)",
        color="#C8C3F5", fontsize=11.5, ha="right", va="center")

fig.savefig(OUT / "approach_diagram.png", dpi=100)
print("saved", OUT / "approach_diagram.png")
