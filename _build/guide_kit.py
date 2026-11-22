"""Reusable engine for project guide PDFs (first used by AirlineDataAnalysis-PBI, generalised for RetailPulse-PBI).
A project's make_project_guide.py builds HTML sections with these helpers; render() prints them to PDF with
Microsoft Edge (headless), so no PDF library is needed. Copy this file into each new project's _build/ folder."""
import html
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
E = html.escape


@dataclass
class Theme:
    navy: str
    primary: str
    secondary: str
    accent: str
    bad: str
    good: str
    ink: str
    muted: str
    bg: str
    line: str
    row_alt: str
    subtitle: str
    tint: str             # light background for callouts and code chips
    cover_end: str        # cover gradient end colour
    font_head: str = "'Segoe UI Semibold', 'Segoe UI', sans-serif"
    font_body: str = "'Segoe UI', sans-serif"


# ------------------------------------------------------------------ project data readers
def parse_measures(model_def: Path) -> pd.DataFrame:
    """All measures in all tables of a TMDL folder. Handles quoted and unquoted names (Desktop writes both)."""
    rows = []
    for f in sorted((model_def / "tables").glob("*.tmdl")):
        txt = f.read_text(encoding="utf-8")
        found = 0
        for m in re.finditer(r"(?:\t/// (?P<d>[^\n]*)\n)?\tmeasure (?:'(?P<q>[^']+)'|(?P<u>[^'\s=][^=\n]*?)) =[ ]?(?P<e>[^\n]*)\n"
                             r"(?P<body>(?:\t\t\t[^\n]*\n|[ \t]*\n(?=\t\t\t))*)(?P<props>(?:\t\t[^\n]*\n|\n(?=\t\t))*)", txt):
            folder = re.search(r"displayFolder: (.*)", m["props"])
            expr = m["e"].strip() or " ".join(l.strip() for l in m["body"].splitlines() if l.strip())
            rows.append(dict(table=f.stem, name=m["q"] or m["u"], expr=expr, desc=m["d"] or "",
                             folder=folder.group(1) if folder else "(no folder)"))
            found += 1
        expected = len(re.findall(r"^\tmeasure ", txt, re.M))
        assert found == expected, f"{f.name}: parsed {found} of {expected} measures"
    return pd.DataFrame(rows)


def git_commits(root: Path) -> pd.DataFrame:
    out = subprocess.run(["git", "-C", str(root), "log", "--reverse", "--format=%h|%ad|%s", "--date=short"],
                         capture_output=True, text=True, encoding="utf-8").stdout.strip().splitlines()
    df = pd.DataFrame([c.split("|", 2) for c in out], columns=["Commit", "Date", "Message"])
    df["Commit"] = df.Commit.map(lambda c: f"<code>{c}</code>")
    df["Message"] = df.Message.map(E)
    return df


uri = lambda p: Path(p).resolve().as_uri()


# ------------------------------------------------------------------ HTML building blocks
def table(df, cols=None, cls=""):
    cols = cols or list(df.columns)
    head = "".join(f"<th>{E(str(c))}</th>" for c in cols)
    rows = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>" for r in df[cols].itertuples(index=False))
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def section(num, title, lead, body):
    return (f'<section class="page"><div class="sec-head"><span class="sec-num">{num}</span><div><h2>{title}</h2>'
            f'<p class="lead">{lead}</p></div></div>{body}</section>')


def flow(steps, cls="flow"):
    items = []
    for i, (a, b) in enumerate(steps):
        items.append(f'<div class="node"><div class="node-t">{a}</div><div class="node-b">{b}</div></div>')
        if i < len(steps) - 1:
            items.append('<div class="arrow">&#10140;</div>')
    return f'<div class="{cls}">{"".join(items)}</div>'


def callout(title, text, kind="info"):
    return f'<div class="callout {kind}"><b>{title}</b> {text}</div>'


def code(text):
    return f"<pre><code>{E(text)}</code></pre>"


def badge(status):
    return f'<span class="badge {status.lower()}">{status}</span>'


def equation(main, parts, notes=()):
    """main = (label, sub); parts = [(label, sub), ...] joined by x; notes = small chips underneath."""
    boxes = [f'<div class="eqbox big">{main[0]}<br><small>{main[1]}</small></div><div class="op">=</div>']
    for i, (a, b) in enumerate(parts):
        boxes.append(f'<div class="eqbox">{a}<br><small>{b}</small></div>')
        if i < len(parts) - 1:
            boxes.append('<div class="op">&times;</div>')
    out = '<div class="eq">' + "".join(boxes) + "</div>"
    if notes:
        out += '<div class="eq sub">' + "".join(f'<div class="eqbox s">{n}</div>' for n in notes) + "</div>"
    return out


def swatches(items):
    return '<div class="swatches">' + "".join(
        f'<div class="sw"><div class="chip" style="background:{c}"></div><b>{E(n)}</b><br><code>{c}</code></div>' for n, c in items) + "</div>"


def schema_svg(th: Theme, boxes, links, width=900, height=430):
    """boxes: name -> (x, y, w, h, colour, [rows]); links: [((x1, y1), (x2, y2), label)]."""
    s = [f'<svg viewBox="0 0 {width} {height}" class="diagram" xmlns="http://www.w3.org/2000/svg">']
    for (x1, y1), (x2, y2), lab in links:
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{th.secondary}" stroke-width="2.5" stroke-dasharray="6 4"/>')
        s.append(f'<text x="{(x1 + x2) / 2 + 6}" y="{(y1 + y2) / 2 - 6}" font-size="11" fill="{th.muted}">{E(lab)}</text>')
    for name, (x, y, w, h, c, rows) in boxes.items():
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" stroke="{c}" stroke-width="2"/>')
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="10" fill="{c}"/><rect x="{x}" y="{y + 16}" width="{w}" height="10" fill="{c}"/>')
        s.append(f'<text x="{x + 12}" y="{y + 18}" font-size="13" font-weight="700" fill="#fff">{E(name)}</text>')
        for i, r in enumerate(rows):
            s.append(f'<text x="{x + 12}" y="{y + 44 + i * 17}" font-size="12" fill="{th.ink}">{E(r)}</text>')
    s.append("</svg>")
    return "".join(s)


def cover(th: Theme, kicker, title, subtitle, stats, image, meta, band=None):
    st = "".join(f"<div><b>{v}</b><span>{k}</span></div>" for v, k in stats)
    band_html = f'<img class="cover-band" src="{band}">' if band else '<div class="cover-bar"></div>'
    return (f'<section class="cover">{band_html}<div class="cover-inner"><div class="kicker">{kicker}</div><h1>{E(title)}</h1>'
            f'<p class="cover-sub">{subtitle}</p><div class="stats">{st}</div><img class="cover-img" src="{image}">'
            f'<p class="meta">{meta}</p></div></section>')


# ------------------------------------------------------------------ styles + rendering
def css(th: Theme, footer):
    return f"""
@page {{ size: A4; margin: 14mm 14mm 16mm 14mm;
  @bottom-left {{ content: "{footer}"; font: 8pt 'Segoe UI'; color: {th.muted}; }}
  @bottom-right {{ content: counter(page); font: 8pt 'Segoe UI'; color: {th.muted}; }} }}
@page :first {{ margin: 0; @bottom-left {{ content: none; }} @bottom-right {{ content: none; }} }}
* {{ box-sizing: border-box; }}
body {{ font-family: {th.font_body}; font-size: 9.6pt; color: {th.ink}; margin: 0; line-height: 1.45;
        -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
h1, h2, h3, .sec-num, .stats b, .node-t, .eqbox, .toc {{ font-family: {th.font_head}; }}
section.page {{ page-break-before: always; }}
.cover {{ height: 297mm; background: linear-gradient(160deg, {th.navy} 0%, {th.navy} 55%, {th.cover_end} 100%); color: #fff; }}
.cover-band {{ width: 100%; display: block; }} .cover-bar {{ height: 6px; background: {th.accent}; }}
.cover-inner {{ padding: 22mm 18mm 0 18mm; }}
.kicker {{ color: {th.accent}; letter-spacing: 3px; text-transform: uppercase; font: 600 11pt {th.font_head}; }}
.cover h1 {{ font-size: 34pt; margin: 6px 0 10px; }}
.cover-sub {{ font-size: 12pt; color: {th.subtitle}; max-width: 150mm; }}
.stats {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin: 14mm 0 10mm; }}
.stats div {{ background: rgba(255,255,255,.08); border-top: 3px solid {th.accent}; border-radius: 6px; padding: 8px 10px; }}
.stats b {{ display: block; font-size: 18pt; }} .stats span {{ color: {th.subtitle}; font-size: 8.5pt; }}
.cover-img {{ width: 100%; border-radius: 8px; box-shadow: 0 6px 24px rgba(0,0,0,.35); }}
.meta {{ color: {th.subtitle}; font-size: 9pt; margin-top: 8mm; }}
.sec-head {{ display: flex; gap: 12px; align-items: flex-start; border-bottom: 3px solid {th.accent}; padding-bottom: 6px; margin-bottom: 10px; }}
.sec-num {{ background: {th.navy}; color: #fff; min-width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center;
           justify-content: center; font-size: 14pt; }}
h2 {{ margin: 0; font-size: 18pt; color: {th.navy}; }} h3 {{ color: {th.primary}; font-size: 11.5pt; margin: 12px 0 4px; }}
.lead {{ margin: 2px 0 0; color: {th.muted}; }}
table {{ width: 100%; border-collapse: collapse; margin: 6px 0 10px; font-size: 8.6pt; }}
th {{ background: {th.navy}; color: #fff; text-align: left; padding: 5px 6px; font-weight: 600; }}
td {{ border-bottom: 1px solid {th.line}; padding: 4px 6px; vertical-align: top; }}
tr:nth-child(even) td {{ background: {th.row_alt}; }}
table.small {{ font-size: 7.8pt; }} table.code code {{ font-size: 7.2pt; }}
code, pre {{ font-family: Consolas, monospace; }}
pre {{ background: {th.navy}; color: #EEF0FA; padding: 8px 10px; border-radius: 6px; font-size: 8pt; white-space: pre-wrap; border-left: 4px solid {th.accent}; }}
td code, p code, li code, .lead code {{ background: {th.tint}; padding: 0 3px; border-radius: 3px; }}
.badge {{ padding: 1px 6px; border-radius: 8px; font-size: 7.5pt; font-weight: 700; color: #fff; }}
.badge.pass {{ background: {th.good}; }} .badge.warn {{ background: #E6A700; }} .badge.fail {{ background: {th.bad}; }}
.callout {{ border-left: 4px solid {th.primary}; background: {th.tint}; padding: 6px 10px; border-radius: 4px; margin: 8px 0; }}
.callout.warn {{ border-color: {th.bad}; background: #FFF1EA; }} .callout.ok {{ border-color: {th.good}; background: #E6F5F3; }}
.flow {{ display: flex; align-items: stretch; gap: 4px; margin: 8px 0 12px; }} .flow.wrap {{ flex-wrap: wrap; row-gap: 8px; }}
.flow .node {{ flex: 1; background: #fff; border: 1.5px solid {th.primary}; border-top: 5px solid {th.primary}; border-radius: 6px; padding: 5px 7px; min-width: 22mm; }}
.flow .node:nth-child(4n+3) {{ border-top-color: {th.accent}; }}
.node-t {{ color: {th.navy}; font-size: 9pt; font-weight: 600; }} .node-b {{ color: {th.muted}; font-size: 7.8pt; }}
.arrow {{ color: {th.secondary}; font-size: 14pt; display: flex; align-items: center; }}
.flow.vertical {{ flex-direction: column; gap: 0; }}
.flow.vertical .node {{ display: flex; gap: 10px; border-top-width: 1.5px; border-left: 5px solid {th.primary}; }}
.flow.vertical .node-t {{ min-width: 38mm; }} .flow.vertical .arrow {{ transform: rotate(90deg); justify-content: center; height: 14px; font-size: 10pt; }}
img {{ max-width: 100%; }} img.full {{ width: 100%; border: 1px solid {th.line}; border-radius: 6px; margin-top: 8px; }}
img.half {{ width: 60%; }} img.portrait {{ width: 70mm; border-radius: 6px; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-items: start; }} .two img {{ width: 100%; border: 1px solid {th.line}; border-radius: 6px; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }} figure {{ margin: 0; }}
figure img {{ border: 1px solid {th.line}; border-radius: 6px; }} figcaption {{ color: {th.muted}; font-size: 8pt; text-align: center; }}
svg.diagram {{ width: 100%; height: auto; font-family: 'Segoe UI'; margin: 4px 0 8px; }}
.eq {{ display: flex; align-items: center; justify-content: center; gap: 10px; margin: 8px 0; }}
.eqbox {{ background: {th.primary}; color: #fff; border-radius: 8px; padding: 8px 14px; text-align: center; font-size: 11pt; }}
.eqbox.big {{ background: {th.navy}; font-size: 14pt; border-bottom: 4px solid {th.accent}; }} .eqbox small {{ font: 8pt 'Segoe UI'; color: #ECE8FF; }}
.eqbox.s {{ background: {th.tint}; color: {th.navy}; font-size: 9pt; padding: 4px 10px; }}
.op {{ font: 700 18pt 'Segoe UI'; color: {th.accent}; }}
.swatches {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin: 8px 0; }}
.sw {{ font-size: 7.5pt; }} .chip {{ height: 26px; border-radius: 6px; border: 1px solid {th.line}; margin-bottom: 3px; }}
.toc {{ columns: 2; font-size: 11pt; color: {th.navy}; }} .toc li {{ margin: 6px 0; }} .lessons li {{ margin: 6px 0; }}
"""


def toc(items):
    return "<ol class='toc'>" + "".join(f"<li>{x}</li>" for x in items) + "</ol>"


def render(th: Theme, title, footer, sections, html_path: Path, pdf_path: Path):
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{E(title)}</title><style>{css(th, footer)}</style></head>"
           f"<body>{''.join(sections)}</body></html>")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(doc, encoding="utf-8")
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                    "--virtual-time-budget=8000", f"--print-to-pdf={pdf_path}", html_path.as_uri()], capture_output=True, text=True)
    if not pdf_path.exists():
        raise RuntimeError("Edge did not create the PDF")
    print("PDF:", pdf_path, f"{pdf_path.stat().st_size:,} bytes")
