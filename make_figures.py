"""
make_figures.py: draws the figures from the tables analyze.py wrote (nothing is recalculated), with
Altair. Run from the project folder, after analyze.py:   python3 make_figures.py

Saves PNG (300 dpi) and SVG files to results/analysis:
  fig0_representative_images   typical before/after image per treatment (green), one fixed display range
  fig1_fluorescence            MAIN: mean bead fluorescence per well before/after, and the change
  fig2_every_bead              every bead's signal (log scale), before and after, split by well
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
ORDER, CTRL, SAT = list(S.TREATMENTS), S.CONTROL, S.SATURATION

# ---- style: sizes are in points (1 chart unit = 1 pt), so PNGs are saved at 300/72 scale = 300 dpi ----
INK, INK2, BEFORE, EDGE, GRID = "#0b0b0b", "#52514e", "#b4b2a9", "#c3c2b7", "#e1e0d9"
COLOR = {"Buffer only": "#898781", "Probe 0.25": "#6da7ec", "Probe 0.5": "#2a78d6", "Probe 1": "#184f95"}
FONT = "Arial, Helvetica, sans-serif"             # a list, so a missing font falls back instead of vanishing
FILL = alt.Fill("treatment:N", scale=alt.Scale(domain=ORDER, range=[COLOR[t] for t in ORDER]), legend=None)
OPEN = dict(shape="circle", filled=True, fill="white", stroke=COLOR[CTRL], strokeWidth=1.5, size=45, opacity=1)
FILLED = dict(shape="circle", filled=True, stroke="white", strokeWidth=1.2, size=45, opacity=1)
n_wells = wells["treatment"].value_counts()
XT = {i: [t, f"(n = {n_wells[t]} wells)"] for i, t in enumerate(ORDER)}
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


def x_axis(mapping, size=9):
    """x axis with a label (a list of strings = several lines) at each tick value."""
    expr = '""'
    for value, lab in reversed(list(mapping.items())):
        expr = f"abs(datum.value - {value}) < 1e-6 ? {json.dumps(lab, ensure_ascii=False)} : {expr}"
    return alt.Axis(values=list(mapping), labelExpr=expr, title=None, grid=False, labelFontSize=size,
                    labelColor=INK2, labelAngle=0, labelPadding=4)


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

# ---- Figure 0: representative images (chosen by rule in analyze.py), shown in green -----------------
(OUT / "representative_images").mkdir(exist_ok=True)
SIDE = 215                                         # panel size in points
grid = []                                          # one row of panels per timepoint
for tp in ("before", "after"):
    panels = []
    for t in ORDER:
        r = reps[(reps["treatment"] == t) & (reps["timepoint"] == tp)].iloc[0]
        png = RESULTS / "figure_images" / f"{Path(r['file']).stem}_fluor.png"   # exported by the macro
        g = Image.open(png).convert("RGB").getchannel("G")
        black = Image.new("L", g.size, 0)
        img = Image.merge("RGB", (black, g, black))              # grey to green, like Fiji's Green LUT
        img.save(OUT / "representative_images" / png.name)      # full-resolution copy
        img.thumbnail((1024, 1024), Image.LANCZOS)               # ample for a 3-inch panel at 300 dpi
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        layers = [alt.Chart(pd.DataFrame({"u": [uri]})).mark_image(width=SIDE, height=SIDE).encode(
                      url="u:N", x=alt.value(SIDE / 2), y=alt.value(SIDE / 2)),
                  # well and position in white inside the image, so labels never overlap
                  text_at(f"{r['well']}, position {r['position']}", 0.03 * SIDE, 0.03 * SIDE,
                          align="left", baseline="top", fontSize=8, color="white")]
        if t == ORDER[0]:                          # row label on the left
            layers.append(text_at(tp.capitalize(), -6, SIDE / 2, angle=270, baseline="bottom", fontSize=10, color=INK))
        panel = alt.layer(*layers).properties(width=SIDE, height=SIDE)
        panels.append(panel.properties(title=title(t)) if tp == "before" else panel)
    grid.append(alt.hconcat(*panels, spacing=8))
display = re.search(r"figure display range=([^\n]+)", (RESULTS / "settings_used.txt").read_text(encoding="utf-8"))[1]
save(alt.vconcat(*grid, spacing=6).properties(title=title(
    "Representative images: typical well and image per treatment; display range " + display.replace("Grays", "Green"),
    size=9, weight="normal", color=INK2, anchor="middle", offset=8)), "fig0_representative_images")

# ---- Figure 1 (main): mean bead fluorescence per well, before/after (left) and the change (right) ------
W1, H1 = 330, 215
pos = wells["treatment"].map(ORDER.index)
wells["xb"], wells["xa"] = pos - 0.18, pos + 0.18                        # before and after columns
wells["xd"] = pos + wells.groupby("treatment")["well"].transform(lambda s: np.linspace(-0.08, 0.08, len(s)))


def X(field):
    return alt.X(f"{field}:Q", scale=XSCALE, axis=x_axis(XT))


# left: before (open) and after (filled) value of each well, joined by a line; short bar = mean
means = pd.DataFrame([{"x": w[x].iat[0] - 0.08, "x2": w[x].iat[0] + 0.08, "y": w[col].mean()}
                      for _, w in wells.groupby("treatment", sort=False)
                      for x, col in (("xb", "F_before"), ("xa", "F_after"))])
dom1 = [10 ** v for v in padded(np.log10(wells[["F_before", "F_after"]].min().min()),
                                np.log10(wells[["F_before", "F_after"]].max().max()))]
scale1 = alt.Scale(type="log", domain=dom1, nice=False)


def Y1(field):
    return alt.Y(f"{field}:Q", scale=scale1, axis=log_axis(*dom1, YLAB))


one = pd.DataFrame({"n": [0]})
left = alt.layer(
    minor_ticks(*dom1, scale1),
    alt.Chart(wells).mark_rule(color=EDGE, strokeWidth=1).encode(X("xb"), Y1("F_before"), x2="xa:Q", y2="F_after:Q"),
    alt.Chart(wells).mark_point(**OPEN).encode(X("xb"), Y1("F_before")),
    alt.Chart(wells).mark_point(**FILLED).encode(X("xa"), Y1("F_after"), fill=FILL),
    alt.Chart(means).mark_rule(color=INK, strokeWidth=1.6).encode(X("x"), Y1("y"), x2="x2:Q"),
    # legend in the upper left, placed in points
    alt.Chart(one).mark_point(**OPEN).encode(x=alt.value(16), y=alt.value(12)),
    alt.Chart(one).mark_point(**FILLED, fill=COLOR["Probe 0.5"]).encode(x=alt.value(16), y=alt.value(29)),
    text_at("Before", 30, 12, align="left", baseline="middle", fontSize=9, color=INK),
    text_at("After", 30, 29, align="left", baseline="middle", fontSize=9, color=INK),
).properties(width=W1, height=H1, title=title("Mean bead fluorescence per well, before and after (log scale)"))

# right: each well's change; bar = mean ± SD of the wells
bars = []
for i, t in enumerate(ORDER):
    v = wells.loc[wells["treatment"] == t, "dF"].to_numpy()
    m, sd = v.mean(), v.std(ddof=1)
    bars.append({"x": i + 0.28, "mean": m, "lo": m - sd, "hi": m + sd})
bars = pd.DataFrame(bars)
dom2 = padded(*[f(np.concatenate([wells["dF"], bars["lo"], bars["hi"]])) for f in (np.min, np.max)])


def Y2(field):
    return alt.Y(f"{field}:Q", scale=alt.Scale(domain=dom2, nice=False, zero=False),
                 axis=alt.Axis(title="After − before (counts)", values=nice_ticks(*dom2), format="d"))


right = alt.layer(
    alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=EDGE, strokeWidth=1).encode(Y2("y")),
    alt.Chart(bars).mark_rule(color=INK, strokeWidth=1.2).encode(X("x"), Y2("lo"), y2="hi:Q"),
    *[alt.Chart(bars).mark_tick(orient="horizontal", size=size, thickness=1.2, color=INK).encode(X("x"), Y2(f))
      for f, size in (("lo", 6), ("hi", 6), ("mean", 14))],
    alt.Chart(wells).mark_point(**{**FILLED, "strokeWidth": 1.5, "size": 55}).encode(X("xd"), Y2("dF"), fill=FILL),
).properties(width=W1, height=H1, title=title("Change in bead fluorescence per well"))

sat = wells[wells["treatment"] != CTRL].groupby("treatment")["pct_saturated_after"].mean()
note = ["Each dot is one well (mean of its images). Right: bar = mean ± SD of the wells.",
        f"Probe-well values are lower bounds: {sat.min():.0f} to {sat.max():.0f}% of their beads "
        f"reach the detector maximum, which caps their signal (see fig2)."]
save(alt.hconcat(left, right, spacing=40).properties(title=footnote(note)), "fig1_fluorescence")

# ---- Figure 2: every bead, log scale, split by well ------------------------------------------------------
W2, H2 = 470, 245
rng = np.random.default_rng(0)                     # fixed seed: the same jitter every run
dots, ticks = [], {}
for i, t in enumerate(ORDER):
    wl = sorted(beads.loc[beads["treatment"] == t, "well"].unique())
    offs = np.linspace(-0.11, 0.11, len(wl))
    for tp, dx in (("before", -0.22), ("after", 0.22)):
        for k, well in enumerate(wl):
            F = beads.loc[(beads["treatment"] == t) & (beads["timepoint"] == tp) & (beads["well"] == well), "F"]
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
    alt.Chart(pd.concat(dots, ignore_index=True)).mark_circle(size=7, opacity=0.7, strokeWidth=0).encode(
        alt.X("x:Q", scale=XSCALE, axis=x_axis(ticks, size=8)), alt.Y("y:Q", scale=scale3),
        color=alt.Color("col:N", scale=None)),
    # label for the detector-maximum line, just right of the plot
    alt.Chart(pd.DataFrame({"y": [SAT], "t": ["detector\nmaximum"]})).mark_text(
        align="left", baseline="middle", lineBreak="\n", fontSize=8, color=INK2).encode(
        x=alt.value(W2 + 6), y=alt.Y("y:Q", scale=scale3), text="t:N"),
    # treatment names under the before/after labels
    alt.Chart(pd.DataFrame({"x": list(XT), "t": ["\n".join(v) for v in XT.values()]})).mark_text(
        baseline="top", lineBreak="\n", fontSize=9, color=INK).encode(
        x=alt.X("x:Q", scale=XSCALE), y=alt.value(H2 + 22), text="t:N"),
).properties(width=W2, height=H2, title=title("Every bead before and after treatment (each narrow column is one well)"))
save(alt.vconcat(fig2).properties(title=footnote("Log scale; values at or below 1 are shown at 1.", size=7)),
     "fig2_every_bead")

print(f"Figures done. In {OUT}")
