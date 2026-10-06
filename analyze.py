"""
analyze.py: turns the Fiji macro's bead measurements into per-well before/after results and
statistics. Settings are in settings.py; figures are drawn by make_figures.py.

Each well's after-treatment beads are compared with the same well's before-treatment beads. The
two days show different fields of view, so bead populations are compared, not individual beads.

Run from the project folder, after the Fiji macro:   python3 analyze.py

Writes to results/analysis:
  file_labels.csv            how every file name was read and which images were used (check this first)
  bead_table.csv             every bead used, labelled
  image_summary.csv          one row per image
  well_summary.csv           one row per well (the replicate)
  treatment_summary.csv      mean, SD and 95% CI per treatment
  representative_images.csv  typical before/after image per treatment, for fig0
  stats_report.txt           the printed report, including the tests
"""
import platform
import re
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats

import settings as S

RESULTS = Path("results")
OUT = RESULTS / "analysis"
OUT.mkdir(exist_ok=True)
beads = pd.read_csv(RESULTS / "bead_measurements.csv")
log = pd.read_csv(RESULTS / "segmentation_log.csv", index_col="file")
ORDER = list(S.TREATMENTS)
MAX = S.MAX_IMAGES_PER_WELL
report = []


def say(msg=""):
    print(msg)
    report.append(msg)


def fmt_p(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


def mean_ci(v):
    """Mean, SD and 95% confidence interval (t distribution) of a set of well values."""
    m, sd, n = v.mean(), v.std(), len(v)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return m, sd, m - half, m + half


# ---- 1. read the file names and choose the images --------------------------------------------------------------------
# AD_2026.09.23-BW1.1 = before (B), well 1, position 1
# AD_2026.09.24_AP0.5W1.1_0001 = after (A), well 1, position 1, second save (P0.5 is ignored: see settings.py)
NAME = re.compile(r"[_-]([AB]).*[.W](\d+)\.(\d+)(?:_(\d+))?$")
parsed = []
for f in beads["file"].unique():
    tp, well, pos, rep = NAME.search(Path(f).stem).groups()
    parsed.append([f, "before" if tp == "B" else "after", int(well), int(pos), int(rep or 0)])
files = pd.DataFrame(parsed, columns=["file", "timepoint", "well", "position", "repeat"]).set_index("file")
files["treatment"] = files["well"].map(S.PLATE_MAP)
files["well_name"] = "W" + files["well"].astype(str)
files["n_beads"] = beads.groupby("file").size()
files["status"] = [S.EXCLUDE.get(f, "used") for f in files.index]

# at most MAX images per well and timepoint: most beads first, then the originally named field of a
# position (an extra field saved as _0001 is field 1, labelled "b"), then the lowest position
used = files[files["status"] == "used"].sort_values("repeat")
used["field"] = used.groupby(["timepoint", "well", "position"]).cumcount()
used = used.sort_values(["n_beads", "field", "position"], ascending=[False, True, True])
over = used.groupby(["timepoint", "well"]).cumcount() >= MAX
files.loc[used.index[over], "status"] = f"more than {MAX} images in the well; fewest beads"
used = used[~over]
used["image"] = (used["well_name"] + "." + used["position"].astype(str)
                 + used["field"].map(lambda k: "abcdefgh"[k] if k else ""))
files.reset_index().to_csv(OUT / "file_labels.csv", index=False)
say("Images not used:\n" + "\n".join(f"  {f}: {why}" for f, why in files["status"].items() if why != "used"))
counts = used.groupby(["well_name", "timepoint"]).size().unstack()
say(f"Wells with fewer than {MAX} images:\n" + counts[(counts < MAX).any(axis=1)].to_string())

# ---- 2. per-bead measures ------------------------------------------------------------------------
beads = beads.merge(used[["timepoint", "treatment", "well", "well_name", "position", "image"]].reset_index(),
                    on="file")
beads["dose"] = beads["treatment"].map(S.TREATMENTS)
beads["F"] = beads["ring_mean"] - beads["bg_mean"]           # counts above local background
beads["SNR"] = beads["F"] / beads["bg_sd"]
beads["saturated"] = beads["disc_max"] >= S.SATURATION
beads.to_csv(OUT / "bead_table.csv", index=False)

# ---- 3. images, then wells (the replicate) --------------------------------------------------------
keys = ["treatment", "dose", "well", "well_name", "timepoint"]
img = beads.groupby(keys + ["image", "position"]).agg(
    file=("file", "first"), n_beads=("F", "size"), F=("F", "mean"), SNR=("SNR", "mean"), bg=("bg_mean", "mean"),
    pct_saturated=("saturated", "mean")).reset_index()
img["pct_saturated"] *= 100
img.to_csv(OUT / "image_summary.csv", index=False)

per_tp = img.groupby(keys)[["F", "SNR", "bg", "pct_saturated", "n_beads"]].mean()
per_tp["n_images"] = img.groupby(keys).size()
wells = per_tp.unstack("timepoint")
wells.columns = [f"{m}_{tp}" for m, tp in wells.columns]
wells = wells.reset_index()
wells["dF"] = wells["F_after"] - wells["F_before"]
wells["treatment"] = pd.Categorical(wells["treatment"], ORDER, ordered=True)
wells = wells.sort_values(["treatment", "well"]).reset_index(drop=True)
wells.to_csv(OUT / "well_summary.csv", index=False)

n = img.assign(oof=img["file"].map(log["out_of_focus"])).groupby("timepoint").agg(
    images=("file", "size"), beads=("n_beads", "sum"), oof=("oof", "sum")).loc[["before", "after"]]
n["found"] = n["beads"] + n["oof"]                           # beads found before the focus checks
say(f"Wells compared: {len(wells)}; images before/after: {n.images.before}/{n.images.after}; "
    f"beads before/after: {n.beads.before}/{n.beads.after}")
say("Out-of-focus beads left out by the Fiji macro (transmitted-light focus checks): " + "; ".join(
    f"{tp} {r.oof} of {r.found} ({100 * r.oof / r.found:.0f}%)" for tp, r in n.iterrows()))

# ---- 4. treatment summary ----------------------------------------------------------------------------
rows = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    row = {"treatment": t, "dose": S.TREATMENTS[t], "n_wells": len(w)}
    for k in ["F_before", "F_after", "dF", "SNR_before", "SNR_after", "bg_before", "bg_after", "pct_saturated_after"]:
        row.update(zip([f"{k}_mean", f"{k}_sd", f"{k}_ci95_low", f"{k}_ci95_high"], mean_ci(w[k])))
    rows.append(row)
summary = pd.DataFrame(rows)
summary.to_csv(OUT / "treatment_summary.csv", index=False)
say("\nSignal = ring mean minus local background (counts).")
say(summary[["treatment", "n_wells", "F_before_mean", "F_after_mean", "dF_mean", "SNR_before_mean",
             "SNR_after_mean", "bg_after_mean", "pct_saturated_after_mean"]].round(1).to_string(index=False))

# ---- 5. statistics on well values ----------------------------------------------------------------------
# The well is the replicate; outcome = each well's change in bead fluorescence (dF). Two tests, each
# answering one question of the study (reasons in README.md), plus the mean change with 95% CI:
#   Test 1  Dunnett's test: each probe concentration vs buffer (did the probe do more than buffer?)
#   Test 2  linear regression on log2 concentration, probe wells only (does the effect grow with dose?)
say("\nStatistics: well values (the replicate); outcome = each well's change from its own before images.")
say("\n=== Bead fluorescence (change in counts above background) ===")
say("Change from before to after in each treatment (mean of the wells with 95% CI; a description, not a test)")
for r in summary.itertuples():
    say(f"  {r.treatment:12s} {r.dF_mean:8.1f} counts  (95% CI {r.dF_ci95_low:.1f} to {r.dF_ci95_high:.1f}; "
        f"SD {r.dF_sd:.1f}; n = {r.n_wells} wells)")
dF = {t: wells.loc[wells["treatment"] == t, "dF"].to_numpy() for t in ORDER}
probes = [t for t in ORDER if t != S.CONTROL]
d = stats.dunnett(*[dF[t] for t in probes], control=dF[S.CONTROL], random_state=0)
ci = d.confidence_interval()
say(f"Test 1. Did each probe concentration change the beads more than buffer alone? "
    f"(Dunnett's test, corrected for {len(probes)} comparisons)")
for i, t in enumerate(probes):
    say(f"  {t:12s} {dF[t].mean() - dF[S.CONTROL].mean():8.1f} counts more than buffer "
        f"(95% CI {ci.low[i]:.1f} to {ci.high[i]:.1f}), p = {fmt_p(d.pvalue[i])}")
probe_wells = wells[wells["treatment"] != S.CONTROL]
lr = stats.linregress(np.log2(probe_wells["dose"]), probe_wells["dF"])
half = stats.t.ppf(0.975, len(probe_wells) - 2) * lr.stderr
say("Test 2. Does the change grow with concentration? (linear regression on log2 concentration, probe wells only)")
say(f"  slope {lr.slope:.1f} counts per doubling of concentration (95% CI {lr.slope - half:.1f} to "
    f"{lr.slope + half:.1f}), R² = {lr.rvalue ** 2:.2f}, p = {fmt_p(lr.pvalue)}, n = {len(probe_wells)} wells")
say("  Caution: beads at the detector maximum have their signal capped (pct_saturated_after), which "
    "flattens this slope. A flat slope does not show that binding is independent of concentration.")

# ---- 6. representative images, chosen by rule: the typical well, then its typical image -------------------
reps = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    i = (w["dF"] - w["dF"].median()).abs().idxmin()          # well whose change is closest to the median
    for tp in ("before", "after"):
        cand = img[(img["well"] == w.at[i, "well"]) & (img["timepoint"] == tp)]
        target = w.at[i, f"F_{tp}"]
        r = cand.loc[(cand["F"] - target).abs().idxmin()]    # image closest to the well mean
        reps.append({"treatment": t, "timepoint": tp, "well": r["well_name"], "position": r["position"],
                     "file": r["file"], "image_mean_F": round(r["F"], 1), "well_mean_F": round(target, 1)})
pd.DataFrame(reps).to_csv(OUT / "representative_images.csv", index=False)

say(f"\nSoftware: Python {platform.python_version()}, numpy {np.__version__}, "
    f"pandas {pd.__version__}, scipy {scipy.__version__}")
(OUT / "stats_report.txt").write_text("\n".join(report), encoding="utf-8")
print(f"\nAnalysis done. Results in {OUT}")
