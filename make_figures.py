"""
make_figures.py: makes all figures from the tables analyze.py wrote, using Altair. Run it again as
often as you like to adjust figures; nothing is recalculated.

Run from the project folder, after analyze.py:   python3 make_figures.py

Figures (PNG at 300 dpi + SVG) in results/analysis:
  fig0_representative_images   typical before/after image per treatment, one fixed display range
  fig1_fluorescence            MAIN: mean bead fluorescence per well before/after, and the change
  fig2_every_bead              every bead's signal (log scale), before and after, split by well
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

OUT = Path("results/analysis")
FIG_IMAGES = Path("results/figure_images")        # the macro's fluorescence images
beads = pd.read_csv(OUT / "bead_table.csv")
wells = pd.read_csv(OUT / "well_summary.csv")
reps = pd.read_csv(OUT / "representative_images.csv")
ORDER, CTRL, SAT, COLOR = S.ORDER, S.CONTROL, S.SATURATION, S.COLORS

# ---- style: sizes are in points (1 chart unit = 1 pt), so PNGs are saved at 300/72 scale = 300 dpi ----
INK, INK2, BEFORE, EDGE, GRID = "#0b0b0b", "#52514e", "#b4b2a9", "#c3c2b7", "#e1e0d9"
FONT = "Arial, Helvetica, sans-serif"             # a list, so a missing font falls back instead of vanishing
DPI_SCALE = 300 / 72
n_wells = wells.groupby("treatment").size().to_dict()
XT = {i: [t, f"(n = {n_wells[t]} wells)"] for i, t in enumerate(ORDER)}
YLAB = ["Bead fluorescence, ring", "(counts above background)"]
XDOM = [-0.5, len(ORDER) - 0.5]
alt.data_transformers.disable_max_rows()
vl_convert.register_font_directory("/mnt/c/Windows/Fonts")   # Python runs in WSL: use the Windows fonts (Arial)


def title(text, size=10, weight=600, color=INK, **kw):
    return alt.TitleParams(text, fontSize=size, fontWeight=weight, color=color, font=FONT, **kw)


def footnote(lines, size=7.5):
    """Small grey note under the whole figure, right-aligned."""
    return title(lines, size=size, weight="normal", color=INK2, orient="bottom", anchor="end", align="right",
                 offset=10)


def label_expr(mapping):
    """Vega expression that maps tick values to labels (a list of strings = several lines)."""
    expr = '""'
    for value, lab in reversed(list(mapping.items())):
        expr = f"abs(datum.value - {value}) < 1e-6 ? {json.dumps(lab, ensure_ascii=False)} : {expr}"
    return expr


def x_axis(mapping, size=9, color=INK2):
    return alt.Axis(values=list(mapping), labelExpr=label_expr(mapping), title=None, grid=False,
                    labelFontSize=size, labelColor=color, labelAngle=0, labelPadding=4)


def log_axis(lo, hi, axis_title):
    """Log axis with ticks at powers of 10 (labelled 1, 10, 100, 1000: plain digits render in any font)."""
    ticks = {10.0 ** e: f"{10.0 ** e:g}" for e in range(math.ceil(math.log10(lo)), math.floor(math.log10(hi)) + 1)}
    return alt.Axis(values=list(ticks), labelExpr=label_expr(ticks), title=axis_title)


def minor_ticks(lo, hi, y_scale):
    """Short unlabelled ticks at 2 to 9 x each power of 10, left of a log axis (minor ticks)."""
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


def padded_log_domain(values, margin=0.05):
    lo, hi = np.log10(np.min(values)), np.log10(np.max(values))
    r = hi - lo
    return [10 ** (lo - margin * r), 10 ** (hi + margin * r)]


def padded_domain(values, margin=0.05):
    lo, hi = float(np.min(values)), float(np.max(values))
    r = hi - lo
    return [lo - margin * r, hi + margin * r]


def styled(chart):
    return (chart.configure(font=FONT, background="white", padding=6)
            .configure_view(stroke=None)
            .configure_axis(domainColor=EDGE, tickColor=INK2, tickSize=3.5, labelColor=INK2, labelFontSize=9,
                            titleColor=INK2, titleFontSize=9, titleFontWeight="normal", gridColor=GRID,
                            gridWidth=0.8, labelFont=FONT, titleFont=FONT)
            .configure_axisX(grid=False)
            .configure_axisY(grid=True))


def save(chart, name):
    chart = styled(chart)
    chart.save(OUT / f"{name}.png", scale_factor=DPI_SCALE)
    chart.save(OUT / f"{name}.svg")
    print(f"  {name}")


def color_scale():
    return alt.Scale(domain=ORDER, range=[COLOR[t] for t in ORDER])


def paired_wells(before_col, after_col, y_scale, y_axis, width, height, panel_title, extra=()):
    """Before (open) and after (filled) value of each well, joined by a line; short bar = mean."""
    pts, lines, means = [], [], []
    for i, t in enumerate(ORDER):
        w = wells[wells["treatment"] == t]
        xb, xa = i - 0.18, i + 0.18
        for r in w.itertuples():
            yb, ya = getattr(r, before_col), getattr(r, after_col)
            lines.append({"x": xb, "x2": xa, "y": yb, "y2": ya})
            pts.append({"x": xb, "y": yb, "kind": "Before", "treatment": t, "well": r.well_name})
            pts.append({"x": xa, "y": ya, "kind": "After", "treatment": t, "well": r.well_name})
        for x, col in ((xb, before_col), (xa, after_col)):
            means.append({"x": x - 0.08, "x2": x + 0.08, "y": w[col].mean()})
    pts, lines, means = pd.DataFrame(pts), pd.DataFrame(lines), pd.DataFrame(means)
    X = alt.X("x:Q", scale=alt.Scale(domain=XDOM, nice=False), axis=x_axis(XT))
    Y = alt.Y("y:Q", scale=y_scale, axis=y_axis)
    tip = [alt.Tooltip("well:N", title="Well"), alt.Tooltip("treatment:N", title="Treatment"),
           alt.Tooltip("kind:N", title="Timepoint"), alt.Tooltip("y:Q", title="Value", format=".1f")]
    line_layer = alt.Chart(lines).mark_rule(color=EDGE, strokeWidth=1).encode(X, Y, x2="x2:Q", y2="y2:Q")
    before = alt.Chart(pts[pts["kind"] == "Before"]).mark_point(
        shape="circle", filled=True, fill="white", stroke=COLOR[CTRL], strokeWidth=1.5, size=45, opacity=1
    ).encode(X, Y, tooltip=tip)
    after = alt.Chart(pts[pts["kind"] == "After"]).mark_point(
        shape="circle", filled=True, stroke="white", strokeWidth=1.2, size=45, opacity=1
    ).encode(X, Y, fill=alt.Fill("treatment:N", scale=color_scale(), legend=None), tooltip=tip)
    mean_layer = alt.Chart(means).mark_rule(color=INK, strokeWidth=1.6).encode(X, Y, x2="x2:Q")
    # legend in the upper left, placed in pixels
    one = pd.DataFrame({"n": [0]})
    legend = alt.layer(
        alt.Chart(one).mark_point(shape="circle", filled=True, fill="white", stroke=COLOR[CTRL],
                                  strokeWidth=1.5, size=45, opacity=1).encode(x=alt.value(16), y=alt.value(12)),
        alt.Chart(one).mark_point(shape="circle", filled=True, fill=COLOR["Probe 0.5"], stroke="white",
                                  strokeWidth=1.2, size=45, opacity=1).encode(x=alt.value(16), y=alt.value(29)),
        alt.Chart(one).mark_text(text="Before", align="left", baseline="middle", fontSize=9, color=INK)
        .encode(x=alt.value(30), y=alt.value(12)),
        alt.Chart(one).mark_text(text="After", align="left", baseline="middle", fontSize=9, color=INK)
        .encode(x=alt.value(30), y=alt.value(29)),
    )
    return alt.layer(*extra, line_layer, before, after, mean_layer, legend).properties(
        width=width, height=height, title=title(panel_title))


print("Making figures:")

# ---- Figure 0: representative images (chosen by rule in analyze.py) ---------------------------
rep_dir = OUT / "representative_images"
rep_dir.mkdir(exist_ok=True)
SIDE = 215                                          # panel size in points
rows = []
for i, tp in enumerate(("before", "after")):
    panels = []
    for j, t in enumerate(ORDER):
        r = reps[(reps["treatment"] == t) & (reps["timepoint"] == tp)].iloc[0]
        png = FIG_IMAGES / f"{Path(r['file']).stem}_fluor.png"
        img = Image.open(png).convert("RGB")
        zero = Image.new("L", img.size, 0)          # grey to green: keep only the green channel, like Fiji's Green LUT
        img = Image.merge("RGB", (zero, img.getchannel("G"), zero))
        img.save(rep_dir / png.name)                # full-resolution copy
        small = img.copy()
        small.thumbnail((1024, 1024), Image.LANCZOS)   # ample for a 3-inch panel at 300 dpi
        buf = io.BytesIO()
        small.save(buf, format="PNG")
        uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        layers = [
            alt.Chart(pd.DataFrame({"u": [uri], "x": [0.5], "y": [0.5]})).mark_image(width=SIDE, height=SIDE)
            .encode(url="u:N", x=alt.X("x:Q", scale=alt.Scale(domain=[0, 1]), axis=None),
                    y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 1]), axis=None)),
            # well and position, inside the image at the top left (white), so labels never overlap
            alt.Chart(pd.DataFrame({"t": [f"{r['well']}, position {r['position']}"]}))
            .mark_text(align="left", baseline="top", fontSize=8, color="white")
            .encode(text="t:N", x=alt.value(0.03 * SIDE), y=alt.value(0.03 * SIDE)),
        ]
        if j == 0:                                  # row label on the left
            layers.append(alt.Chart(pd.DataFrame({"t": [tp.capitalize()]}))
                          .mark_text(angle=270, baseline="bottom", fontSize=10, color=INK)
                          .encode(text="t:N", x=alt.value(-6), y=alt.value(SIDE / 2)))
        panel = alt.layer(*layers).properties(width=SIDE, height=SIDE)
        if i == 0:
            panel = panel.properties(title=title(t))
        panels.append(panel)
    rows.append(alt.hconcat(*panels, spacing=8))
# display range and scale bar as set in bead_segmentation.ijm (FIG_MIN, FIG_MAX, BAR_UM)
fig0 = alt.vconcat(*rows, spacing=6).properties(
    title=title("Representative images: typical well and image per treatment; display range 0-4000 "
                "(Green, linear, identical for all images)", size=9, weight="normal", color=INK2,
                anchor="middle", offset=8))
save(fig0, "fig0_representative_images")

# ---- Figure 1 (main): bead fluorescence per well, before/after and the change ------------------------
W1, H1 = 330, 215
f_vals = np.concatenate([wells["F_before"], wells["F_after"]])
YDOM1 = padded_log_domain(f_vals)
Y1 = alt.Scale(type="log", domain=YDOM1, nice=False)
left = paired_wells("F_before", "F_after", Y1, log_axis(*YDOM1, YLAB), W1, H1,
                    "Mean bead fluorescence per well, before and after (log scale)",
                    extra=[minor_ticks(*YDOM1, Y1)])
dots, bars = [], []
for i, t in enumerate(ORDER):
    w = wells[wells["treatment"] == t]
    v = w["dF"].to_numpy()
    for x, (val, name) in zip(i + np.linspace(-0.08, 0.08, len(v)), zip(v, w["well_name"])):
        dots.append({"x": x, "y": val, "treatment": t, "well": name})
    m, sd = v.mean(), v.std(ddof=1)
    bars.append({"x": i + 0.28, "mean": m, "lo": m - sd, "hi": m + sd, "treatment": t})
dots, bars = pd.DataFrame(dots), pd.DataFrame(bars)
dom = padded_domain(np.concatenate([dots["y"], bars["lo"], bars["hi"]]))
X = alt.X("x:Q", scale=alt.Scale(domain=XDOM, nice=False), axis=x_axis(XT))
Yq = alt.Scale(domain=dom, nice=False, zero=False)
yax = alt.Axis(title="After − before (counts)", values=nice_ticks(*dom), format="d")
right = alt.layer(
    alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=EDGE, strokeWidth=1).encode(y=alt.Y("y:Q", scale=Yq, axis=yax)),
    alt.Chart(bars).mark_rule(color=INK, strokeWidth=1.2).encode(X, alt.Y("lo:Q", scale=Yq, axis=yax), y2="hi:Q"),
    alt.Chart(bars).mark_tick(orient="horizontal", size=6, thickness=1.2, color=INK).encode(X, alt.Y("lo:Q", scale=Yq, axis=yax)),
    alt.Chart(bars).mark_tick(orient="horizontal", size=6, thickness=1.2, color=INK).encode(X, alt.Y("hi:Q", scale=Yq, axis=yax)),
    alt.Chart(bars).mark_tick(orient="horizontal", size=14, thickness=1.2, color=INK).encode(
        X, alt.Y("mean:Q", scale=Yq, axis=yax),
        tooltip=[alt.Tooltip("treatment:N", title="Treatment"), alt.Tooltip("mean:Q", title="Mean", format=".1f")]),
    alt.Chart(dots).mark_point(shape="circle", filled=True, stroke="white", strokeWidth=1.5, size=55, opacity=1).encode(
        X, alt.Y("y:Q", scale=Yq, axis=yax), fill=alt.Fill("treatment:N", scale=color_scale(), legend=None),
        tooltip=[alt.Tooltip("well:N", title="Well"), alt.Tooltip("y:Q", title="Change", format=".1f")]),
).properties(width=W1, height=H1, title=title("Change in bead fluorescence per well"))
sat = wells[wells["treatment"] != CTRL].groupby("treatment")["pct_saturated_after"].mean()
note = ["Each dot is one well (mean of its images). Right: bar = mean ± SD of the wells.",
        f"Probe-well values are lower bounds: {sat.min():.0f} to {sat.max():.0f}% of their beads "
        f"reach the detector maximum, which caps their signal (see fig2)."]
save(alt.hconcat(left, right, spacing=40).properties(title=footnote(note)), "fig1_fluorescence")

# ---- Figure 2: every bead, log scale, split by well ---------------------------------------------
W2, H2 = 470, 245
rng_ = np.random.default_rng(0)                    # fixed seed, so the jitter is the same every run
rows, ticks = [], {}
for i, t in enumerate(ORDER):
    wl = sorted(beads.loc[beads["treatment"] == t, "well"].unique())
    offs = np.linspace(-0.11, 0.11, len(wl))
    for tp, dx in (("before", -0.22), ("after", 0.22)):
        for k, wnum in enumerate(wl):
            sel = beads[(beads["treatment"] == t) & (beads["timepoint"] == tp) & (beads["well"] == wnum)]
            x = i + dx + offs[k] + rng_.uniform(-0.022, 0.022, len(sel))
            rows.append(pd.DataFrame({"x": x, "y": sel["F"].clip(lower=1).to_numpy(), "F": sel["F"].to_numpy(),
                                      "col": BEFORE if tp == "before" else COLOR[t], "treatment": t,
                                      "timepoint": tp, "well": f"W{wnum}"}))
        ticks[round(i + dx, 6)] = tp
pts = pd.concat(rows, ignore_index=True)
YDOM2 = [0.8, SAT * 1.6]
Y2 = alt.Scale(type="log", domain=YDOM2, nice=False)
X2 = alt.X("x:Q", scale=alt.Scale(domain=XDOM, nice=False), axis=x_axis(ticks, size=8))
fig2 = alt.layer(
    minor_ticks(*YDOM2, Y2),
    alt.Chart(pd.DataFrame({"y": [SAT]})).mark_rule(color=EDGE, strokeWidth=1).encode(
        y=alt.Y("y:Q", scale=Y2, axis=log_axis(*YDOM2, YLAB))),
    alt.Chart(pts).mark_circle(size=7, opacity=0.7, strokeWidth=0).encode(
        X2, alt.Y("y:Q", scale=Y2), color=alt.Color("col:N", scale=None),
        tooltip=[alt.Tooltip("well:N", title="Well"), alt.Tooltip("timepoint:N", title="Timepoint"),
                 alt.Tooltip("F:Q", title="Signal", format=".1f")]),
    # label for the detector-maximum line, just right of the plot
    alt.Chart(pd.DataFrame({"y": [SAT], "t": ["detector\nmaximum"]})).mark_text(
        align="left", baseline="middle", lineBreak="\n", fontSize=8, color=INK2).encode(
        x=alt.value(W2 + 6), y=alt.Y("y:Q", scale=Y2), text="t:N"),
    # treatment names under the before/after labels
    alt.Chart(pd.DataFrame({"x": list(XT), "t": ["\n".join(v) for v in XT.values()]})).mark_text(
        baseline="top", lineBreak="\n", fontSize=9, color=INK).encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=XDOM, nice=False)), y=alt.value(H2 + 22), text="t:N"),
).properties(width=W2, height=H2,
             title=title("Every bead before and after treatment (each narrow column is one well)"))
save(alt.vconcat(fig2).properties(title=footnote(
    "Log scale; values at or below 1 are shown at 1.", size=7)),
    "fig2_every_bead")

print(f"Figures done. In {OUT}")
