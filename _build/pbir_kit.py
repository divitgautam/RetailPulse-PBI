"""Shared PBIR helpers (first written for RetailPulse-PBI, extended in AirlineDataAnalysis-PBI): palette, field/literal helpers, Page builder, theme writer.
Usage: import pbir_kit as k; k.init(report_folder); build Page objects; k.finish(pages)."""
import json, shutil, sys
from pathlib import Path

REPORT = DEF = PAGES = None


def init(report_path):
    """Point the kit at a <Project>.Report folder."""
    global REPORT, DEF, PAGES
    REPORT = Path(report_path); DEF = REPORT / "definition"; PAGES = DEF / "pages"
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
MOBILE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainerMobileState/2.9.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

# ---------- palette ----------
# InXiteOut brand (inxiteout.ai): deep navy, violet primary, lilac secondary; orange for warnings
NAVY, TEAL, AMBER, CORAL, SLATE, GREEN = "#030734", "#682EFF", "#CD83FF", "#F05100", "#62748E", "#009588"
FONT, FONT_BOLD = "'Instrument Sans', 'Segoe UI', sans-serif", "'Instrument Sans', 'Segoe UI Semibold', sans-serif"
INK, MUTED, BG, LINE, WHITE = "#020618", "#62748E", "#F1F5F9", "#E2E8F0", "#FFFFFF"
W, H, M, G = 1280, 720, 16, 12  # page size, margin, gutter
SUBTITLE, ROW_ALT, EXTRA_COLORS = "#C8C3F5", "#F6F3FF", ["#AC24FF", "#FCBB00"]
THEME_NAME, THEME_FILE = "InXiteOut", "InxiteOut.json"
HEADER_IMAGE, HEADER_TEXT_X = None, 0   # optional SVG banner behind the header text
IMAGES = {}                              # name -> SVG text, registered as report images


def set_theme(**kw):
    """Override palette/theme globals, e.g. set_theme(NAVY="#0A2540", THEME_NAME="Runway")."""
    g = globals()
    for k_, v_ in kw.items():
        if k_ not in g: raise KeyError(k_)
        g[k_] = v_


def image_ref(item):
    return {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": item}}}


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
PLAIN_CARD = {"accentBar": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],   # new card without its inner box
              "outline": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
              "fillCustom": [{"properties": {"show": L(False)}}]}
NO_CHROME = {"background": [{"properties": {"show": L(False)}}], "border": [{"properties": {"show": L(False)}}],
             "title": [{"properties": {"show": L(False)}}], "visualHeader": [{"properties": {"show": L(False)}}],
             "dropShadow": [{"properties": {"show": L(False)}}]}


class Page:
    def __init__(self, name, display, page_type=None, hidden=False, binding=None, filters=None, size=None):
        self.name, self.display, self.visuals, self.z = name, display, [], 0
        self.page_type, self.hidden, self.binding, self.filters = page_type, hidden, binding, filters
        self.w, self.h = size or (W, H)

    def add(self, name, vtype, x, y, w, h, roles=None, title=None, subtitle=None, objects=None,
            sort=None, filters=None, container=None, alt=None, tooltip_page=None):
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
            # a measure field makes a dynamic title (field-value formatting); a string is a fixed title
            vco["title"] = [{"properties": {"show": L(True), "text": L(title) if isinstance(title, str) else {"expr": title}, "fontSize": L(11),
                                            "fontColor": C(INK), "bold": L(True)}}]
        if subtitle:
            vco["subTitle"] = [{"properties": {"show": L(True), "text": L(subtitle), "fontSize": L(9),
                                               "fontColor": C(MUTED)}}]
        vco.update(container or {})
        ttl = title if isinstance(title, str) else None
        alt = alt or (f"{ttl}. {subtitle}" if ttl and subtitle else ttl or subtitle)
        if alt:   # screen-reader text (accessibility)
            vco.setdefault("general", []).append({"properties": {"altText": L(alt[:250])}})
        if tooltip_page:
            vco["visualTooltip"] = [{"properties": {"show": L(True), "type": L("ReportPage"), "section": L(tooltip_page),
                                                    "showChartSpecificTooltips": L(False)}}]
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
    def header(self, title, subtitle, width=W - 2 * M, title_measure=None, title_w=None):
        """title_measure: a measure whose text replaces the fixed title, so the headline follows the slicers."""
        if HEADER_IMAGE:
            self.add("hdr_art", "image", 0, 0, W, 72,
                     objects={"general": [{"properties": {"imageUrl": image_ref(HEADER_IMAGE)}}],
                              "imageScaling": [{"properties": {"imageScalingType": L("Fill")}}]},
                     container={"background": [{"properties": {"show": L(False)}}], "border": [{"properties": {"show": L(False)}}],
                                "padding": [{"properties": {"top": L(0), "bottom": L(0), "left": L(0), "right": L(0)}}],
                                "title": [{"properties": {"show": L(False)}}], "visualHeader": [{"properties": {"show": L(False)}}]})
        self.add("hdr_band", "textbox", HEADER_TEXT_X, 0, W - HEADER_TEXT_X, 72, alt=f"Page title: {title}", objects={"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": " " if title_measure else title, "textStyle": {"fontWeight": "bold", "fontSize": "16pt", "color": WHITE,
                                                          "fontFamily": FONT_BOLD}}]},
            {"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "10pt", "color": SUBTITLE}}]}]}}]},
            container={"background": [{"properties": {"show": not HEADER_IMAGE and L(True) or L(False), "color": C(NAVY), "transparency": L(0)}}],
                       "border": [{"properties": {"show": L(False)}}],
                       "padding": [{"properties": {"top": L(8), "left": L(16)}}]})
        if title_measure:   # dynamic headline drawn over the band, in the same place and style as the fixed title
            self.add("hdr_title", "cardVisual", HEADER_TEXT_X - 5, 4, title_w or (W - HEADER_TEXT_X - 2 * M), 38,
                     roles={"Data": [(title_measure, "Headline")]}, alt=f"Page headline: {title}",
                     objects={**PLAIN_CARD, "label": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                              "value": [{"properties": {"fontSize": L(16), "fontColor": C(WHITE), "fontFamily": L(FONT_BOLD), "bold": L(True)},
                                         "selector": {"id": "default"}}]},
                     container={**NO_CHROME, "padding": [{"properties": {"top": L(0), "bottom": L(0), "left": L(6), "right": L(0)}}]})

    def slicer(self, name, field, label, x, w):
        self.add(name, "slicer", x, 8, w, 56, roles={"Values": [field]}, alt=f"{label} filter",
                 objects={"data": [{"properties": {"mode": L("Dropdown")}}],
                          "header": [{"properties": {"show": L(True), "text": L(label), "fontColor": C(MUTED),
                                                     "textSize": L(9)}}],
                          "items": [{"properties": {"fontColor": C(INK), "textSize": L(10)}}]},
                 container={"background": [{"properties": {"show": L(True), "color": C(WHITE), "transparency": L(0)}}],
                            "border": [{"properties": {"show": L(True), "color": C(LINE), "radius": L(6)}}],
                            "padding": [{"properties": {"top": L(2), "bottom": L(2), "left": L(8), "right": L(8)}}]})

    def cards(self, items, y=80, h=88, filters=None, small=(), x0=M, width=None):
        """items: (name, value field, label[, change-line field, change-line colour field])."""
        n = len(items)
        width = width or W - 2 * M
        cw = (width - (n - 1) * G) / n
        for i, it in enumerate(items):
            name, field, label = it[:3]
            x = round(x0 + i * (cw + G))
            self.add(name, "cardVisual", x, y, round(cw), h,
                     roles={"Data": [(field, label)]}, filters=filters, alt=f"{label} card",
                     objects={"accentBar": [{"properties": {"show": L(True), "color": C(TEAL if i % 2 == 0 else AMBER)},
                                             "selector": {"id": "default"}}],
                              "outline": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                              "label": [{"properties": {"fontSize": L(10)}, "selector": {"id": "default"}}],
                              "value": [{"properties": {"fontSize": L(14 if name in small else 22)}, "selector": {"id": "default"}}]})
            if len(it) > 3:   # change line ("▲ 24.6% vs last year") overlaid at the bottom of the card
                self.add(name + "_d", "cardVisual", x + 4, y + h - 28, round(cw) - 8, 24,
                         roles={"Data": [(it[3], label + " change")]}, filters=filters, alt=f"{label} change",
                         objects={**PLAIN_CARD,
                                  "label": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                                  "value": [{"properties": {"fontSize": L(9), "fontColor": {"solid": {"color": {"expr": it[4]}}}},
                                             "selector": {"id": "default"}}]},
                         container={**NO_CHROME, "padding": [{"properties": {"top": L(0), "bottom": L(0), "left": L(12), "right": L(4)}}]})

    def footer(self, field, nav=True):
        """Source / refresh / caveat line, plus a page navigator on the right."""
        fy = self.h - 32
        self.add("ftr_text", "cardVisual", M, fy, 780 if nav else self.w - 2 * M, 30, roles={"Data": [(field, "Source")]},
                 alt="Report footer: data source, refresh date and caveat",
                 objects={**PLAIN_CARD,
                          "label": [{"properties": {"show": L(False)}, "selector": {"id": "default"}}],
                          "value": [{"properties": {"fontSize": L(8), "fontColor": C(MUTED)}, "selector": {"id": "default"}}]},
                 container={**NO_CHROME, "padding": [{"properties": {"top": L(0), "bottom": L(0), "left": L(0), "right": L(0)}}]})
        if nav:
            zero = {"expr": {"Literal": {"Value": "0L"}}}
            self.add("ftr_nav", "pageNavigator", self.w - M - 460, fy, 460, 30, alt="Page navigation",
                     objects={"text": [{"properties": {"fontSize": L(8), "topMargin": zero, "bottomMargin": zero,
                                                       **({"fontColor": C(WHITE)} if s == "selected" else {})}, "selector": {"id": s}}
                                       for s in ("default", "hover", "press", "selected")],
                              "pages": [{"properties": {"showHiddenPages": L(False)}}]},
                     container={**NO_CHROME})

    def textbox(self, name, x, y, w, h, title, lines, accent=None, size="10pt", gap=False):
        accent = accent or TEAL   # read at call time so set_theme() applies
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
        self.add(name, "textbox", x, y, w, h, alt=title, objects={"general": [{"properties": {"paragraphs": paras}}]},
                 container={"padding": [{"properties": {"top": L(10), "left": L(14), "right": L(14)}}]})

    def write(self):
        pdir = PAGES / self.name
        if pdir.exists():
            shutil.rmtree(pdir)
        (pdir / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE_SCHEMA, "name": self.name, "displayName": self.display, "displayOption": "FitToPage",
                "height": self.h, "width": self.w,
                "objects": {"background": [{"properties": {"color": C(BG), "transparency": L(0)}}],
                            "outspace": [{"properties": {"color": C(BG)}}]}}
        if self.page_type: page["type"] = self.page_type
        if self.hidden: page["visibility"] = "HiddenInViewMode"
        if self.binding: page["pageBinding"] = self.binding
        if self.filters: page["filterConfig"] = {"filters": self.filters}
        (pdir / "page.json").write_text(json.dumps(page, indent=2), encoding="utf-8")
        mobile = self.mobile_positions() if self.page_type != "Tooltip" else {}
        for v in self.visuals:
            d = pdir / "visuals" / v["name"]
            d.mkdir()
            (d / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
            if v["name"] in mobile:
                x, y, w_, h_ = mobile[v["name"]]
                (d / "mobile.json").write_text(json.dumps({"$schema": MOBILE_SCHEMA, "position": {
                    "x": x, "y": y, "z": v["position"]["z"], "height": h_, "width": w_, "tabOrder": v["position"]["tabOrder"]}}, indent=2),
                    encoding="utf-8")

    def mobile_positions(self, mw=324, gap=8):
        """Phone layout (canvas 324 px wide): header, slicers, KPI cards two per row with their change lines, then each
        chart/table/text full width in desktop reading order (top-to-bottom, left-to-right), footer last."""
        pos, y = {}, 0
        by = {v["name"]: v for v in self.visuals}
        for n in ("hdr_art", "hdr_band"):
            if n in by: pos[n] = (0, 0, mw, 110)
        if "hdr_title" in by: pos["hdr_title"] = (6, 4, mw - 12, 50)
        y = 116
        slicers = [v for v in self.visuals if v["visual"]["visualType"] == "slicer"]
        for i, v in enumerate(slicers):
            sw = (mw - gap * (len(slicers) - 1)) / len(slicers)
            pos[v["name"]] = (round(i * (sw + gap)), y, round(sw), 56)
        if slicers: y += 56 + gap
        cards = [v for v in self.visuals if v["visual"]["visualType"] == "cardVisual" and not v["name"].endswith("_d")
                 and not v["name"].startswith(("ftr_", "hdr_")) and v["position"]["y"] < 200]
        cw = (mw - gap) / 2
        for i, v in enumerate(cards):
            cx, cy = round((i % 2) * (cw + gap)), y + (i // 2) * (88 + gap)
            pos[v["name"]] = (cx, cy, round(cw), 88)
            if v["name"] + "_d" in by:
                pos[v["name"] + "_d"] = (cx + 4, cy + 60, round(cw) - 8, 24)
        if cards: y += ((len(cards) + 1) // 2) * (88 + gap)
        rest = sorted((v for v in self.visuals if v["name"] not in pos and not v["name"].endswith("_d")
                       and not v["name"].startswith("ftr_") and v["name"] not in ("btn_back",)),
                      key=lambda v: (v["position"]["y"], v["position"]["x"]))
        for v in rest:
            h_ = 320 if v["visual"]["visualType"] == "textbox" and v["position"]["height"] > 300 else 260
            pos[v["name"]] = (0, y, mw, h_)
            y += h_ + gap
        if "btn_back" in by: pos["btn_back"] = (mw - 90, 70, 90, 36)
        if "ftr_text" in by: pos["ftr_text"] = (0, y, mw, 44); y += 44 + gap
        if "ftr_nav" in by: pos["ftr_nav"] = (0, y, mw, 34)
        return pos




def finish(pages):
    """Write all pages, page order and the InXiteOut theme."""
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
        "name": THEME_NAME,
        "dataColors": [TEAL, AMBER, NAVY, CORAL, SLATE, GREEN] + EXTRA_COLORS,
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
            # the Fluent 2 base theme draws smooth curves, which invent values between points; draw straight segments
            "lineChart": {"*": {"lineStyles": [{"lineChartType": "linear"}]}},
            "pivotTable": {"*": {
                "columnHeaders": [{"backColor": {"solid": {"color": NAVY}}, "fontColor": {"solid": {"color": WHITE}}, "fontSize": 10}],
                "values": [{"fontSize": 10, "backColorSecondary": {"solid": {"color": ROW_ALT}}}],
                "subTotals": [{"rowSubtotals": True}],
                "total": [{"fontColor": {"solid": {"color": NAVY}}}],
            }},
        },
    }
    rr = REPORT / "StaticResources" / "RegisteredResources"
    rr.mkdir(parents=True, exist_ok=True)
    (rr / THEME_FILE).write_text(json.dumps(theme, indent=2), encoding="utf-8")
    for img, svg in IMAGES.items():
        (rr / img).write_text(svg, encoding="utf-8")

    rj = DEF / "report.json"
    rep = json.loads(rj.read_text(encoding="utf-8"))
    base = rep["themeCollection"]["baseTheme"]
    rep["themeCollection"]["customTheme"] = {"name": THEME_FILE, "reportVersionAtImport": base["reportVersionAtImport"],
                                             "type": "RegisteredResources"}
    pk = [r for r in rep["resourcePackages"] if r["name"] != "RegisteredResources"]
    pk.append({"name": "RegisteredResources", "type": "RegisteredResources",
               "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]
                        + [{"name": img, "path": img, "type": "Image"} for img in IMAGES]})
    rep["resourcePackages"] = pk
    rj.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print("pages:", [pg.name for pg in pages], "visuals:", sum(len(pg.visuals) for pg in pages))
