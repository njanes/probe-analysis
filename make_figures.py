"""
make_figures.py: draws the figures from the tables analyze.py wrote (nothing is recalculated), with
Altair. Run from the project folder, after analyze.py:   python3 make_figures.py

Saves PNG (300 dpi) and SVG files to results/analysis:
  fig0_representative_images   typical before/after image per treatment (green), one fixed display range
  fig1_dilution_response       each well's change as % of the strongest dilution, mean ± SD, fitted curve
  fig2_before_after            mean fluorescence before and after, for the treatments in settings.BEFORE_AFTER
  fig3_positive_beads          % of beads positive after treatment, for the dilutions in settings.POSITIVE_BEADS
  fig4_change_per_well         each well's change in fluorescence (after − before), mean ± SD
and figures.html, every figure on one page (images embedded, so the file opens and can be shared on its own).
"""
import base64
import io
import json
import math
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import vl_convert
from PIL import Image

import settings as S

RESULTS = Path("results")
OUT = RESULTS / "analysis"
wells = pd.read_csv(OUT / "well_summary.csv")
reps = pd.read_csv(OUT / "representative_images.csv")
fit = pd.read_csv(OUT / "dilution_fit.csv").iloc[0]
tests = pd.read_csv(OUT / "figure_tests.csv")
ORDER = list(dict.fromkeys(wells["treatment"]))  # treatments in display order, as analyze.py sorted the wells
PROBES = [t for t in ORDER if t.startswith(S.KINDS["probe"])]

# ---- style: sizes are in points (1 chart unit = 1 pt), so PNGs are saved at 300/72 scale = 300 dpi ----
INK, INK2, EDGE, GRID = "#0b0b0b", "#52514e", "#c3c2b7", "#e1e0d9"
GREY, DARK_GREY = "#898781", "#5f5e5a"
BLUES = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95"]
RGB = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in BLUES])
COLOR = {t: GREY if t == S.KINDS["buffer"] else DARK_GREY for t in ORDER if t not in PROBES}   # controls grey
for t, at in zip(PROBES, np.linspace(0, len(BLUES) - 1, len(PROBES))):  # probe blues darken with less dilution
    COLOR[t] = "#" + "".join(f"{round(np.interp(at, range(len(BLUES)), ch)):02x}" for ch in RGB.T)
FONT = "Arial, Helvetica, sans-serif"             # a list, so a missing font falls back instead of vanishing
CSCALE = alt.Scale(domain=ORDER, range=[COLOR[t] for t in ORDER])
FILL = alt.Fill("treatment:N", scale=CSCALE, legend=None)
FILLED = dict(shape="circle", filled=True, stroke="white", strokeWidth=1.2, size=50, opacity=1)


def x_label(t):
    """A treatment's label, as lines: the probe by its dilution alone ("1:400"), buffer as "Annexin-V",
    and a negative control by its dilution with "Negative control" below it."""
    kind, _, dilution = t.partition(" 1:")
    if kind == S.KINDS["buffer"]:
        return ["Annexin-V"]
    return [f"1:{dilution}"] if kind == S.KINDS["probe"] else [f"1:{dilution}", kind]


if Path("/mnt/c/Windows/Fonts").is_dir():         # running in WSL: use the Windows fonts (e.g. Arial)
    vl_convert.register_font_directory("/mnt/c/Windows/Fonts")


def title(text, size=10, weight=600, color=INK, **kw):
    return alt.TitleParams(text, fontSize=size, fontWeight=weight, color=color, font=FONT, **kw)


def text_at(text, x, y, **style):
    """Text at a fixed position, in points from the panel's top left."""
    return alt.Chart(pd.DataFrame({"t": [text]})).mark_text(**style).encode(text="t:N", x=alt.value(x), y=alt.value(y))


def axis_labels(mapping, size=8, **kw):
    """Axis with a label (a list of strings = several lines) at each tick value."""
    expr = '""'
    for value, lab in reversed(list(mapping.items())):
        expr = f"abs(datum.value - {value}) < 1e-6 ? {json.dumps(lab, ensure_ascii=False)} : {expr}"
    return alt.Axis(values=list(mapping), labelExpr=expr, grid=False, labelFontSize=size, labelColor=INK2,
                    labelAngle=0, labelPadding=4, **kw)


def nice_ticks(lo, hi, max_intervals=9):
    """Tick values at a 1, 2, 2.5 or 5 x 10^n step (a standard 'nice' tick spacing)."""
    raw = (hi - lo) / max_intervals
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return [float(v) for v in np.arange(math.ceil(lo / step) * step, hi + step * 1e-9, step)]


def padded(lo, hi, margin=0.05):
    return [lo - margin * (hi - lo), hi + margin * (hi - lo)]


def spread(n, half):
    """n offsets evenly from -half to +half (one alone sits in the middle), so a treatment's wells sit side by side."""
    return np.linspace(-half, half, n) if n > 1 else np.zeros(n)


def linear_y(lo, hi, axis_title, tick_hi=None):
    """Y encoding builder for a linear axis from lo to hi, with nice tick values up to tick_hi (default hi)."""
    scale = alt.Scale(domain=[lo, hi], nice=False, zero=False)
    axis = alt.Axis(title=axis_title, values=nice_ticks(lo, hi if tick_hi is None else tick_hi), format="d")
    return lambda field: alt.Y(f"{field}:Q", scale=scale, axis=axis)


def error_bars(data, x, Y, mean_width=0):
    """Mean ± SD of the wells: a line from data's lo to hi with end caps, plus a wider tick at the mean if
    mean_width is given. A treatment with a single well has no SD (NaN), so no bar."""
    layers = [alt.Chart(data).mark_rule(color=INK, strokeWidth=1.2).encode(x, Y("lo"), y2="hi:Q")]
    for field, size in (("lo", 6), ("hi", 6), ("mean", mean_width)):
        if size:
            layers.append(alt.Chart(data).mark_tick(orient="horizontal", size=size, thickness=1.2, color=INK, opacity=1)
                          .encode(x, Y(field)))
    return layers


def p_label(p):
    """Significance stars (*** p < 0.001, ** p < 0.01, * p < 0.05, ns = not significant) with the p-value."""
    stars = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
    value = "< 0.0001" if p < 1e-4 else f"= {p:.2g}"
    return f"{stars} (p {value})"


def pair_brackets(pairwise, position, base, step):
    """One bracket per test, between the positions of its two groups: the narrowest lowest, each a step higher."""
    t = pairwise.assign(x1=pairwise["a"].map(position), x2=pairwise["b"].map(position))
    t = t.assign(span=t["x2"] - t["x1"]).sort_values(["span", "x1"])
    return [{"x1": r.x1, "x2": r.x2, "y": base + k * step, "label": p_label(r.p)} for k, r in enumerate(t.itertuples())]


def brackets(rows, x_scale, Y, drop):
    """Significance brackets: a line from x1 to x2 at height y, ends dropping by drop, and the label above."""
    data = pd.DataFrame(rows)
    data["xm"], data["y_end"] = (data["x1"] + data["x2"]) / 2, data["y"] - drop
    rule = alt.Chart(data).mark_rule(color=INK, strokeWidth=0.8)
    return [rule.encode(alt.X("x1:Q", scale=x_scale), Y("y"), x2="x2:Q"),
            *[rule.encode(alt.X(f"{x}:Q", scale=x_scale), Y("y_end"), y2="y:Q") for x in ("x1", "x2")],
            alt.Chart(data).mark_text(baseline="bottom", dy=-1, fontSize=9, color=INK).encode(
                alt.X("xm:Q", scale=x_scale), Y("y"), text="label:N")]


def mean_sd(values):
    """Mean, and mean minus and plus the SD, of a set of well values."""
    m, sd = values.mean(), values.std()
    return {"mean": m, "lo": m - sd, "hi": m + sd}


SAVED = []                                         # figure names, in the order saved, for figures.html


def save(chart, name):
    chart = (chart.configure(font=FONT, background="white", padding=6)
             .configure_view(stroke=None)
             .configure_axis(domainColor=EDGE, tickColor=INK2, tickSize=3.5, labelColor=INK2, labelFontSize=9,
                             titleColor=INK2, titleFontSize=9, titleFontWeight="normal", gridColor=GRID,
                             gridWidth=0.8, labelFont=FONT, titleFont=FONT)
             .configure_axisX(grid=False)
             .configure_axisY(grid=True))
    chart.save(OUT / f"{name}.png", scale_factor=300 / 72)
    chart.save(OUT / f"{name}.svg")
    SAVED.append(name)
    print(f"  {name}")


print("Making figures:")

# ---- Figure 0: representative images (chosen by rule in analyze.py), shown in green, 5 treatments a row ----
(OUT / "representative_images").mkdir(exist_ok=True)
SIDE = 170                                         # panel size in points
rows = []                                          # a before row and an after row for each 5 treatments
for start in range(0, len(ORDER), 5):
    for tp in ("before", "after"):
        panels = []
        for t in ORDER[start:start + 5]:
            r = reps[(reps["treatment"] == t) & (reps["timepoint"] == tp)].iloc[0]
            png = RESULTS / "figure_images" / f"{Path(r['file']).stem}_fluor.png"   # exported by the macro
            g = Image.open(png).convert("RGB").getchannel("G")
            black = Image.new("L", g.size, 0)
            img = Image.merge("RGB", (black, g, black))          # grey to green, like Fiji's Green LUT
            img.save(OUT / "representative_images" / png.name)  # full-resolution copy
            img.thumbnail((1024, 1024), Image.LANCZOS)           # ample for a 2.4-inch panel at 300 dpi
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            layers = [alt.Chart(pd.DataFrame({"u": [uri]})).mark_image(width=SIDE, height=SIDE).encode(
                          url="u:N", x=alt.value(SIDE / 2), y=alt.value(SIDE / 2)),
                      # well and position in white inside the image, so labels never overlap
                      text_at(f"{r['well']}, position {r['position']}", 0.03 * SIDE, 0.03 * SIDE,
                              align="left", baseline="top", fontSize=8, color="white")]
            if t == ORDER[start]:                  # row label on the left
                layers.append(text_at(tp.capitalize(), -6, SIDE / 2, angle=270, baseline="bottom", fontSize=10,
                                      color=INK))
            panel = alt.layer(*layers).properties(width=SIDE, height=SIDE)
            panels.append(panel.properties(title=title(x_label(t), size=9)) if tp == "before" else panel)
        rows.append(alt.hconcat(*panels, spacing=6))
save(alt.vconcat(*rows, spacing=6), "fig0_representative_images")

# ---- Figure 1: dilution-response; each well's change as % of the strongest dilution, with the fitted curve -----
W1, H1 = 520, 260
resp = wells[wells["treatment"].isin(PROBES)].copy()
resp["D"] = resp["treatment"].str.extract(r"1:(\d+)")[0].astype(int)                     # dilution factor, 1:D
resp["x"] = resp["D"] * 10 ** resp.groupby("D")["D"].transform(lambda s: spread(len(s), 0.04))   # side by side
bars1 = pd.DataFrame([{"D": d, **mean_sd(w["dF_pct"])} for d, w in resp.groupby("D")])
dils = sorted(resp["D"].unique(), reverse=True)
dom1x = [dils[0] * 1.6, dils[-1] / 1.6]                       # less diluted to the right
curve = pd.DataFrame({"x": np.logspace(math.log10(dom1x[1]), math.log10(dom1x[0]), 200)})
curve["y"] = fit.bottom + (fit.top - fit.bottom) / (1 + (curve["x"] / fit.D50) ** fit.hill)
# dilution labels; one that would overlap the label before it (at about 4.2 points a character) moves to a
# second line
labels, prev = {}, None                            # prev = (x in points, label) of the last first-line label
for d in dils:
    x, lab = W1 * math.log(dom1x[0] / d) / math.log(dom1x[0] / dom1x[1]), f"1:{d}"
    if prev and x - prev[0] < 2.1 * (len(lab) + len(prev[1])):
        labels[d] = ["", lab]
    else:
        labels[d], prev = lab, (x, lab)
scale1x = alt.Scale(type="log", domain=dom1x, nice=False)
axis1x = axis_labels(labels, size=7.5, labelOverlap=False, title="C2-GFP dilution ratio")
Y1 = linear_y(*padded(min(bars1["lo"].min(), resp["dF_pct"].min(), curve["y"].min(), 0),
                      max(bars1["hi"].max(), resp["dF_pct"].max(), curve["y"].max())), "% fluorescence")
equation = (f"y = {fit.bottom:.1f} + {fit.top - fit.bottom:.1f} / (1 + (D / {fit.D50:.0f})^{fit.hill:.2f})"
            .replace("-", "−") + f"\nD = dilution factor (1:D); R² = {fit.r_squared:.2f}")
fig1 = alt.layer(
    alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=EDGE, strokeWidth=1).encode(Y1("y")),
    alt.Chart(curve).mark_line(color=INK2, strokeWidth=1.2).encode(alt.X("x:Q", scale=scale1x, axis=axis1x), Y1("y")),
    alt.Chart(resp).mark_point(**FILLED).encode(alt.X("x:Q", scale=scale1x), Y1("dF_pct"), fill=FILL),
    *error_bars(bars1, alt.X("D:Q", scale=scale1x), Y1, mean_width=14),
    text_at(equation, 8, 8, align="left", baseline="top", lineBreak="\n", fontSize=8.5, color=INK2),
).properties(width=W1, height=H1)
save(fig1, "fig1_dilution_response")

# ---- Figure 2: mean fluorescence before and after, paired bars ----------------------------------------------
groups = [t for t in ORDER if t in S.BEFORE_AFTER]
W2, H2 = 110 * len(groups), 320
rows = []
for i, t in enumerate(groups):
    w = wells[wells["treatment"] == t]
    for tp, dx in (("before", -0.19), ("after", 0.19)):           # before: open bar; after: filled
        rows.append({"group": i, "timepoint": tp, "x": i + dx, "x0": i + dx - 0.16, "x1": i + dx + 0.16, "zero": 0,
                     **mean_sd(w[f"F_{tp}"]), "fill": "white" if tp == "before" else COLOR[t],
                     "stroke": GREY if tp == "before" else COLOR[t]})
pairs = pd.DataFrame(rows)
scale2x = alt.Scale(domain=[-0.5, len(groups) - 0.5], nice=False)
axis2x = axis_labels(dict(zip(pairs["x"], pairs["timepoint"])), size=7.5, title=None)
# significance: before vs after over each pair (paired t-test), then the probe's after bar vs the negative
# control's (Welch's t-test) above
t2, top = tests[tests["figure"] == "fig2"], pairs[["mean", "hi"]].max().max()
marks = [{"x1": i - 0.19, "x2": i + 0.19, "label": p_label(r.p),
          "y": pairs.loc[pairs["group"] == i, ["mean", "hi"]].max().max() + 0.06 * top}
         for r in t2[t2["test"].str.startswith("paired")].itertuples() for i in [groups.index(r.a)]]
marks += pair_brackets(t2[t2["test"].str.startswith("Welch")], {t: i + 0.19 for i, t in enumerate(groups)},
                       1.2 * top, 0.13 * top)
Y2 = linear_y(min(pairs["lo"].min(), 0), max(m["y"] for m in marks) + 0.12 * top, "Normalized bead fluorescence",
              tick_hi=1.05 * top)
fig2 = alt.layer(
    alt.Chart(pairs).mark_rect(strokeWidth=1.2).encode(
        alt.X("x0:Q", scale=scale2x, axis=axis2x), Y2("mean"), x2="x1:Q", y2="zero:Q",
        fill=alt.Fill("fill:N", scale=None), stroke=alt.Stroke("stroke:N", scale=None)),
    *error_bars(pairs, alt.X("x:Q", scale=scale2x), Y2),
    *brackets(marks, scale2x, Y2, drop=0.025 * top),
    # treatment names under the before/after labels
    alt.Chart(pd.DataFrame({"x": range(len(groups)), "t": ["\n".join(x_label(t)) for t in groups]})).mark_text(
        baseline="top", lineBreak="\n", fontSize=8, color=INK).encode(
        x=alt.X("x:Q", scale=scale2x), y=alt.value(H2 + 20), text="t:N"),
).properties(width=W2, height=H2)
save(fig2, "fig2_before_after")

# ---- Figure 3: % of beads positive after treatment --------------------------------------------------------
groups = [t for t in ORDER if t in S.POSITIVE_BEADS]
W3, H3 = 90 * len(groups), 320
positive = pd.DataFrame([{"x": i, "x0": i - 0.3, "x1": i + 0.3, "zero": 0, "fill": COLOR[t],
                          **mean_sd(wells.loc[wells["treatment"] == t, "pct_positive_after"])}
                         for i, t in enumerate(groups)])
positive[["lo", "hi"]] = positive[["lo", "hi"]].clip(0, 100)      # a percentage stays within 0 to 100
scale3x = alt.Scale(domain=[-0.5, len(groups) - 0.5], nice=False)
axis3x = axis_labels({i: x_label(t) for i, t in enumerate(groups)}, title="C2-GFP dilution ratio")
marks = pair_brackets(tests[tests["figure"] == "fig3"], {t: i for i, t in enumerate(groups)}, 108, 11)
Y3 = linear_y(0, max(m["y"] for m in marks) + 12, "Positive beads (%)", tick_hi=100)
fig3 = alt.layer(
    alt.Chart(positive).mark_rect().encode(alt.X("x0:Q", scale=scale3x, axis=axis3x), Y3("mean"), x2="x1:Q",
                                           y2="zero:Q", fill=alt.Fill("fill:N", scale=None)),
    *error_bars(positive, alt.X("x:Q", scale=scale3x), Y3),
    *brackets(marks, scale3x, Y3, drop=2.5),
).properties(width=W3, height=H3)
save(fig3, "fig3_positive_beads")

# ---- Figure 4: each well's change in fluorescence, with the mean ± SD centred on the wells ------------------
groups = PROBES
W4, H4 = 70 * len(groups), 260
change = wells[wells["treatment"].isin(groups)].copy()
change["x"] = change["treatment"].map(groups.index) + change.groupby("treatment")["well_name"].transform(
    lambda s: spread(len(s), 0.12))                                          # a treatment's wells side by side
bars4 = pd.DataFrame([{"x": i, **mean_sd(change.loc[change["treatment"] == t, "dF"])} for i, t in enumerate(groups)])
scale4x = alt.Scale(domain=[-0.5, len(groups) - 0.5], nice=False)
axis4x = axis_labels({i: x_label(t) for i, t in enumerate(groups)}, title="C2-GFP dilution ratio")
Y4 = linear_y(*padded(min(change["dF"].min(), bars4["lo"].min(), 0), max(change["dF"].max(), bars4["hi"].max())),
              "Δ normalized fluorescence")
fig4 = alt.layer(
    alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=EDGE, strokeWidth=1).encode(Y4("y")),
    alt.Chart(change).mark_point(**FILLED).encode(alt.X("x:Q", scale=scale4x, axis=axis4x), Y4("dF"), fill=FILL),
    *error_bars(bars4, alt.X("x:Q", scale=scale4x), Y4, mean_width=14),
).properties(width=W4, height=H4)
save(fig4, "fig4_change_per_well")

# ---- every figure on one page, each at its printed size (300 dpi PNG shown at 96 CSS pixels per inch) ------
body = ""
for name in SAVED:
    png = OUT / f"{name}.png"
    width = round(Image.open(png).width * 96 / 300)
    body += (f'<figure><img src="data:image/png;base64,{base64.b64encode(png.read_bytes()).decode()}" '
             f'width="{width}" alt="{name}"><figcaption>Figure {name[3]} ({png.name})</figcaption></figure>\n')
(OUT / "figures.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bead analysis figures</title>
<style>
body {{ font-family: {FONT}; background: white; color: {INK}; max-width: 1240px; margin: 32px auto; padding: 0 16px; }}
figure {{ margin: 0 0 48px; }}
img {{ max-width: 100%; height: auto; display: block; }}
figcaption {{ color: {INK2}; font-size: 14px; margin-top: 8px; }}
</style></head><body>
{body}</body></html>
""", encoding="utf-8")
print("  figures.html")

print(f"Figures done. In {OUT}")
