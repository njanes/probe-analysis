"""
make_figures.py: draws the figures from the tables analyze.py wrote (nothing is recalculated), with
Altair. Run from the project folder, after analyze.py:   python3 make_figures.py

Saves PNG (300 dpi) and SVG files to results/analysis:
  fig0_representative_images   typical before/after image per treatment (green), one fixed display range
  fig1_fluorescence            MAIN: mean bead fluorescence per well before/after, and the change
  fig2_every_bead              every bead's signal (log scale), before and after, split by well
  fig3_dilution_response       change per well against probe dilution
"""
import base64
import io
import json
import math
import re
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import vl_convert
from PIL import Image

import settings as S

RESULTS = Path("results")
OUT = RESULTS / "analysis"
beads = pd.read_csv(OUT / "bead_table.csv")
wells = pd.read_csv(OUT / "well_summary.csv")
reps = pd.read_csv(OUT / "representative_images.csv")
ORDER = list(dict.fromkeys(wells["treatment"]))  # treatments in display order, as analyze.py sorted the wells
PROBES = [t for t in ORDER if t.startswith(S.KINDS["probe"])]
SAT = S.SATURATION

# ---- style: sizes are in points (1 chart unit = 1 pt), so PNGs are saved at 300/72 scale = 300 dpi ----
INK, INK2, BEFORE, EDGE, GRID = "#0b0b0b", "#52514e", "#b4b2a9", "#c3c2b7", "#e1e0d9"
GREY, DARK_GREY = "#898781", "#5f5e5a"
BLUES = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95"]
RGB = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in BLUES])
COLOR = {t: GREY if t == S.KINDS["buffer"] else DARK_GREY for t in ORDER if t not in PROBES}   # controls grey
for t, at in zip(PROBES, np.linspace(0, len(BLUES) - 1, len(PROBES))):  # probe blues darken with less dilution
    COLOR[t] = "#" + "".join(f"{round(np.interp(at, range(len(BLUES)), ch)):02x}" for ch in RGB.T)
FONT = "Arial, Helvetica, sans-serif"             # a list, so a missing font falls back instead of vanishing
CSCALE = alt.Scale(domain=ORDER, range=[COLOR[t] for t in ORDER])
FILL = alt.Fill("treatment:N", scale=CSCALE, legend=None)
OPEN = dict(shape="circle", filled=True, fill="white", stroke=GREY, strokeWidth=1.5, size=45, opacity=1)
FILLED = dict(shape="circle", filled=True, stroke="white", strokeWidth=1.2, size=45, opacity=1)
XT = {i: t.rsplit(" ", 1) for i, t in enumerate(ORDER)}                # e.g. ["Probe", "1:400"]
XSCALE = alt.Scale(domain=[-0.5, len(ORDER) - 0.5], nice=False)
YLAB = ["Bead fluorescence, ring", "(counts above background)"]
if Path("/mnt/c/Windows/Fonts").is_dir():         # running in WSL: use the Windows fonts (e.g. Arial)
    vl_convert.register_font_directory("/mnt/c/Windows/Fonts")


def title(text, size=10, weight=600, color=INK, **kw):
    return alt.TitleParams(text, fontSize=size, fontWeight=weight, color=color, font=FONT, **kw)


def footnote(lines, size=7.5):
    """Small grey note under the whole figure, right-aligned."""
    return title(lines, size=size, weight="normal", color=INK2, orient="bottom", anchor="end", align="right",
                 offset=10)


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


def log_axis(lo, hi, axis_title):
    """Log axis with ticks at powers of 10, labelled 1, 10, 100, 1000 (plain digits render in any font)."""
    return alt.Axis(values=[10.0 ** e for e in range(math.ceil(math.log10(lo)), math.floor(math.log10(hi)) + 1)],
                    format="d", title=axis_title)


def minor_ticks(lo, hi, y_scale):
    """Short unlabelled ticks at 2 to 9 x each power of 10, left of a log axis."""
    vals = [m * 10.0 ** e for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1)
            for m in range(2, 10) if lo <= m * 10.0 ** e <= hi]
    return alt.Chart(pd.DataFrame({"y": vals})).mark_rule(color=INK2, strokeWidth=0.6).encode(
        x=alt.value(-2), x2=alt.value(0), y=alt.Y("y:Q", scale=y_scale))


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


def X(field):
    return alt.X(f"{field}:Q", scale=XSCALE, axis=axis_labels(XT, title=None))


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
            panels.append(panel.properties(title=title(t, size=9)) if tp == "before" else panel)
        rows.append(alt.hconcat(*panels, spacing=6))
display = re.search(r"figure display range=([^\n]+)", (RESULTS / "settings_used.txt").read_text(encoding="utf-8"))[1]
save(alt.vconcat(*rows, spacing=6).properties(title=title(
    "Representative images: typical well and image per treatment; display range " + display.replace("Grays", "Green"),
    size=9, weight="normal", color=INK2, anchor="middle", offset=8)), "fig0_representative_images")

# ---- Figure 1 (main): mean bead fluorescence per well, before/after (top) and the change (bottom) -------
W1, H1 = 70 * len(ORDER), 215
pos = wells["treatment"].map(ORDER.index)
wells["xb"], wells["xa"] = pos - 0.18, pos + 0.18                        # before and after columns
wells["xd"] = pos + wells.groupby("treatment")["well_name"].transform(lambda s: spread(len(s), 0.08))

# top: before (open) and after (filled) value of each well, joined by a line; short bar = mean
means = pd.DataFrame([{"x": w[x].iat[0] - 0.08, "x2": w[x].iat[0] + 0.08, "y": w[col].mean()}
                      for _, w in wells.groupby("treatment", sort=False)
                      for x, col in (("xb", "F_before"), ("xa", "F_after"))])
dom1 = [10 ** v for v in padded(np.log10(wells[["F_before", "F_after"]].min().min()),
                                np.log10(wells[["F_before", "F_after"]].max().max()))]
scale1 = alt.Scale(type="log", domain=dom1, nice=False)


def Y1(field):
    return alt.Y(f"{field}:Q", scale=scale1, axis=log_axis(*dom1, YLAB))


one = pd.DataFrame({"n": [0]})
top = alt.layer(
    minor_ticks(*dom1, scale1),
    alt.Chart(wells).mark_rule(color=EDGE, strokeWidth=1).encode(X("xb"), Y1("F_before"), x2="xa:Q", y2="F_after:Q"),
    alt.Chart(wells).mark_point(**OPEN).encode(X("xb"), Y1("F_before")),
    alt.Chart(wells).mark_point(**FILLED).encode(X("xa"), Y1("F_after"), fill=FILL),
    alt.Chart(means).mark_rule(color=INK, strokeWidth=1.6).encode(X("x"), Y1("y"), x2="x2:Q"),
    # legend in the upper left, placed in points
    alt.Chart(one).mark_point(**OPEN).encode(x=alt.value(16), y=alt.value(12)),
    alt.Chart(one).mark_point(**FILLED, fill=COLOR[PROBES[len(PROBES) // 2]]).encode(x=alt.value(16), y=alt.value(29)),
    text_at("Before", 30, 12, align="left", baseline="middle", fontSize=9, color=INK),
    text_at("After", 30, 29, align="left", baseline="middle", fontSize=9, color=INK),
).properties(width=W1, height=H1, title=title("Mean bead fluorescence per well, before and after (log scale)"))

# bottom: each well's change; bar = mean ± SD of the wells
bars = wells.groupby("treatment", sort=False)["dF"].agg(["mean", "std"]).reset_index(drop=True)
bars["x"], bars["lo"], bars["hi"] = bars.index + 0.28, bars["mean"] - bars["std"], bars["mean"] + bars["std"]
# a treatment with a single well has no SD (NaN), so no bar
dom2 = padded(*[f(np.concatenate([wells["dF"], bars["lo"], bars["hi"]])) for f in (np.nanmin, np.nanmax)])


def Y2(field):
    return alt.Y(f"{field}:Q", scale=alt.Scale(domain=dom2, nice=False, zero=False),
                 axis=alt.Axis(title="After − before (counts)", values=nice_ticks(*dom2), format="d"))


bottom = alt.layer(
    alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=EDGE, strokeWidth=1).encode(Y2("y")),
    alt.Chart(bars).mark_rule(color=INK, strokeWidth=1.2).encode(X("x"), Y2("lo"), y2="hi:Q"),
    *[alt.Chart(bars).mark_tick(orient="horizontal", size=size, thickness=1.2, color=INK).encode(X("x"), Y2(f))
      for f, size in (("lo", 6), ("hi", 6), ("mean", 14))],
    alt.Chart(wells).mark_point(**{**FILLED, "strokeWidth": 1.5, "size": 55}).encode(X("xd"), Y2("dF"), fill=FILL),
).properties(width=W1, height=H1, title=title("Change in bead fluorescence per well"))

sat = wells.groupby("treatment")["pct_saturated_after"].mean()
note = ["Each dot is one well (mean of its images). Bottom: bar = mean ± SD of the wells.",
        f"Values are lower bounds where beads reach the detector maximum (up to {sat.max():.0f}% of beads in a "
        f"treatment; see fig2)."]
save(alt.vconcat(top, bottom, spacing=24).properties(title=footnote(note)), "fig1_fluorescence")

# ---- Figure 2: every bead, log scale, split by well ------------------------------------------------------
W2, H2 = 98 * len(ORDER), 245
rng = np.random.default_rng(0)                     # fixed seed: the same jitter every run
dots, ticks = [], {}
for i, t in enumerate(ORDER):
    wl = wells.loc[wells["treatment"] == t, "well_name"].tolist()
    offs = spread(len(wl), 0.11)
    for tp, dx in (("before", -0.22), ("after", 0.22)):
        for k, well in enumerate(wl):
            F = beads.loc[(beads["treatment"] == t) & (beads["timepoint"] == tp) & (beads["well_name"] == well), "F"]
            dots.append(pd.DataFrame({"x": i + dx + offs[k] + rng.uniform(-0.022, 0.022, len(F)),
                                      "y": F.clip(lower=1).to_numpy(),
                                      "col": BEFORE if tp == "before" else COLOR[t]}))
        ticks[round(i + dx, 6)] = tp
dom3 = [0.8, SAT * 1.6]
scale3 = alt.Scale(type="log", domain=dom3, nice=False)
fig2 = alt.layer(
    minor_ticks(*dom3, scale3),
    alt.Chart(pd.DataFrame({"y": [SAT]})).mark_rule(color=EDGE, strokeWidth=1).encode(
        y=alt.Y("y:Q", scale=scale3, axis=log_axis(*dom3, YLAB))),
    alt.Chart(pd.concat(dots, ignore_index=True)).mark_circle(size=6, opacity=0.7, strokeWidth=0).encode(
        alt.X("x:Q", scale=XSCALE, axis=axis_labels(ticks, size=7, title=None)), alt.Y("y:Q", scale=scale3),
        color=alt.Color("col:N", scale=None)),
    # label for the detector-maximum line, just right of the plot
    alt.Chart(pd.DataFrame({"y": [SAT], "t": ["detector\nmaximum"]})).mark_text(
        align="left", baseline="middle", lineBreak="\n", fontSize=8, color=INK2).encode(
        x=alt.value(W2 + 6), y=alt.Y("y:Q", scale=scale3), text="t:N"),
    # treatment names under the before/after labels
    alt.Chart(pd.DataFrame({"x": list(XT), "t": ["\n".join(v) for v in XT.values()]})).mark_text(
        baseline="top", lineBreak="\n", fontSize=8, color=INK).encode(
        x=alt.X("x:Q", scale=XSCALE), y=alt.value(H2 + 20), text="t:N"),
).properties(width=W2, height=H2, title=title("Every bead before and after treatment (each narrow column is one well)"))
save(alt.vconcat(fig2).properties(title=footnote(
    "Log scale; values at or below 1 are shown at 1.", size=7)), "fig2_every_bead")

# ---- Figure 3: dilution-response -------------------------------------------------------------------------
W3, H3 = 520, 260
probe = wells[wells["treatment"].isin(PROBES)].copy()
probe["dilution"] = probe["treatment"].str.extract(r"1:(\d+)")[0].astype(int)
mean3 = probe.groupby("dilution", as_index=False)["dF"].mean()
dils = sorted(probe["dilution"].unique(), reverse=True)
dom3x = [dils[0] * 1.6, dils[-1] / 1.6]                       # less diluted to the right
# dilution labels; one that would overlap the label before it (at about 4.2 points a character) moves to a
# second line
labels, prev = {}, None                            # prev = (x in points, label) of the last first-line label
for d in dils:
    x, lab = W3 * math.log(dom3x[0] / d) / math.log(dom3x[0] / dom3x[1]), f"1:{d}"
    if prev and x - prev[0] < 2.1 * (len(lab) + len(prev[1])):
        labels[d] = ["", lab]
    else:
        labels[d], prev = lab, (x, lab)
X3 = alt.X("dilution:Q", scale=alt.Scale(type="log", domain=dom3x, nice=False),
           axis=axis_labels(labels, size=7.5, labelOverlap=False, title="Probe dilution (more probe to the right)"))
controls = wells[~wells["treatment"].isin(PROBES)].groupby("treatment", as_index=False)["dF"].mean().sort_values("dF")
controls["label"] = controls["treatment"].str.lower()
dom4 = padded(min(probe["dF"].min(), controls["dF"].min(), 0), probe["dF"].max())
scale4 = alt.Scale(domain=dom4, nice=False, zero=False)
Y4 = alt.Y("dF:Q", scale=scale4, axis=alt.Axis(title="After − before (counts)", values=nice_ticks(*dom4), format="d"))
# control labels, in points from the top; each at least 10 points above the one below it
ys = []
for y in H3 * (dom4[1] - controls["dF"]) / (dom4[1] - dom4[0]):
    ys.append(min(y, ys[-1] - 10) if ys else y)
controls["y"] = ys
ctrl_color = alt.Color("treatment:N", scale=CSCALE, legend=None)
fig3 = alt.layer(
    alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=EDGE, strokeWidth=1).encode(y=alt.Y("y:Q", scale=scale4)),
    # the controls have no probe dilution: dashed lines across the plot at their mean change
    alt.Chart(controls).mark_rule(strokeDash=[4, 3], strokeWidth=1.2).encode(
        alt.Y("dF:Q", scale=scale4), color=ctrl_color),
    alt.Chart(controls).mark_text(align="right", baseline="bottom", dy=-2, fontSize=7.5).encode(
        x=alt.value(W3 - 2), y=alt.Y("y:Q", scale=None, axis=None), text="label:N", color=ctrl_color),
    alt.Chart(mean3).mark_line(color=INK2, strokeWidth=1.2).encode(X3, Y4),
    alt.Chart(probe).mark_point(**{**FILLED, "size": 50}).encode(X3, Y4, fill=FILL),
).properties(width=W3, height=H3, title=title("Change in bead fluorescence against probe dilution"))
save(alt.vconcat(fig3).properties(title=footnote(
    ["Each dot is one well; line = mean per dilution. Dashed lines: mean change with each control.",
     f"Values are lower bounds where beads reach the detector maximum (up to {sat.max():.0f}% of beads)."])),
    "fig3_dilution_response")

print(f"Figures done. In {OUT}")
