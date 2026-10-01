"""
analyze.py: reads the Fiji macro's bead measurements and produces the per-well
before/after results and statistics. Figures are made by make_figures.py.

Each well's after-treatment beads are compared with the SAME well's before-treatment
beads. Before and after were imaged on different days, so the fields of view differ;
the comparison is between the bead populations of a well, not individual beads.

Run from the project folder:   python3 analyze.py
Reads results/bead_measurements.csv and writes to results/analysis:
  file_labels.csv            every image: timepoint, well, treatment, used or why not
  bead_table.csv             every bead used, labelled
  image_summary.csv          one row per image
  well_summary.csv           one row per well (the replicate)
  treatment_summary.csv      mean, SD and 95% CI per treatment
  representative_images.csv  typical before/after image per treatment, for fig0
  stats_report.txt           all results and tests, in plain language
"""
import platform
import re
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats

import settings as S

OUT = Path("results/analysis")
OUT.mkdir(exist_ok=True)
report = []


def say(msg=""):
    print(msg)
    report.append(msg)


# ---- 1. label every image -----------------------------------------------------------------
# File names end in <well>.<position>, with _0001 etc. for repeat saves:
# AD_2026.09.23-BW1.1 (before treatment, 23 Sept), AD_2026.09.24_AP0.5W1.1 (after, 24 Sept)
beads = pd.read_csv("results/bead_measurements.csv")
labels = pd.DataFrame({"file": beads["file"].unique()})
well_pos = labels["file"].map(lambda f: re.search(r"(\d+)\.(\d)(?:_\d{4})?$", Path(f).stem).groups())
labels["timepoint"] = np.where(labels["file"].str.contains("2026.09.23", regex=False), "before", "after")
labels["well"] = well_pos.map(lambda wp: int(wp[0]))
labels["position"] = well_pos.map(lambda wp: int(wp[1]))
labels["well_name"] = "W" + labels["well"].astype(str)
labels["treatment"] = labels["well"].map(S.PLATE_MAP)
labels["status"] = labels["file"].map(S.EXCLUDE).fillna("used")
labels.to_csv(OUT / "file_labels.csv", index=False)

say("Read results/bead_measurements.csv")
say("Images not used (settings.EXCLUDE):")
for f, why in S.EXCLUDE.items():
    say(f"  {f}: {why}")
labels = labels[labels["status"] == "used"]
say("Images used per well:\n" + labels.groupby(["well", "timepoint"]).size().unstack().to_string())

beads = beads.merge(labels.drop(columns="status"), on="file")
beads["dose"] = beads["treatment"].map(S.DOSE)

# ---- 2. per-bead measures -------------------------------------------------------------------
beads["F"] = beads["ring_mean"] - beads["bg_mean"]          # bead edge ring, counts above local background
beads["SNR"] = beads["F"] / beads["bg_sd"]
beads["saturated"] = beads["disc_max"] >= S.SATURATION
beads.to_csv(OUT / "bead_table.csv", index=False)

# ---- 3. images, then wells (the replicate) ----------------------------------------------------
keys = ["treatment", "dose", "well", "well_name", "timepoint"]
img = beads.groupby(keys + ["file", "position"]).agg(
    n_beads=("F", "size"), F=("F", "mean"), SNR=("SNR", "mean"), bg=("bg_mean", "mean"),
    pct_saturated=("saturated", "mean")).reset_index()
img["pct_saturated"] *= 100
img.to_csv(OUT / "image_summary.csv", index=False)

per_tp = img.groupby(keys)[["F", "SNR", "bg", "pct_saturated", "n_beads"]].mean()
per_tp["n_images"] = img.groupby(keys).size()
wells = per_tp.unstack("timepoint")
wells.columns = [f"{m}_{tp}" for m, tp in wells.columns]
wells = wells.reset_index()
wells["dF"] = wells["F_after"] - wells["F_before"]
wells["fold"] = wells["F_after"] / wells["F_before"]
before_sd = beads[beads["timepoint"] == "before"].groupby("well")["F"].std()
wells["SNR_change"] = wells["dF"] / wells["well"].map(before_sd)
wells["treatment"] = pd.Categorical(wells["treatment"], S.ORDER, ordered=True)
wells = wells.sort_values(["treatment", "well"]).reset_index(drop=True)
wells.to_csv(OUT / "well_summary.csv", index=False)
n_img = img.groupby("timepoint").size()
n_bead = beads.groupby("timepoint").size()
say(f"Wells compared: {len(wells)}; images before/after: {n_img['before']}/{n_img['after']}; "
    f"beads before/after: {n_bead['before']}/{n_bead['after']}")

# ---- 4. treatment summary ---------------------------------------------------------------------
M = ["F_before", "F_after", "dF", "fold", "SNR_before", "SNR_after", "SNR_change", "bg_before", "bg_after",
     "pct_saturated_after"]
rows = []
for t in S.ORDER:
    w = wells[wells["treatment"] == t]
    n = len(w)
    row = {"treatment": t, "dose": S.DOSE[t], "n_wells": n}
    for k in M:
        m, sd = w[k].mean(), w[k].std()
        half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
        row.update({f"{k}_mean": m, f"{k}_sd": sd, f"{k}_ci95_low": m - half, f"{k}_ci95_high": m + half})
    rows.append(row)
summary = pd.DataFrame(rows)
summary.to_csv(OUT / "treatment_summary.csv", index=False)
say("\nSignal = ring mean minus local background (counts).")
say(summary[["treatment", "n_wells", "F_before_mean", "F_after_mean", "dF_mean", "SNR_before_mean",
             "SNR_after_mean", "bg_after_mean", "pct_saturated_after_mean"]].round(1).to_string(index=False))

# ---- 5. statistics on well values ---------------------------------------------------------------
# The well is the replicate. Outcome = each well's change in bead fluorescence from its own before
# images. Two tests, each answering one question of the study (reasons in README.md):
#   Test 1  Dunnett's test: each probe concentration vs buffer (did the probe do more than buffer?)
#   Test 2  linear regression on log2 concentration, probe wells only (does the effect grow with dose?)
# plus the mean change and 95% CI per treatment, as description.
def fmt_p(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


say("\nStatistics: well values (the replicate); outcome = each well's change from its own before images.")
say("\n=== Bead fluorescence (change in counts above background) ===")
groups = {t: wells.loc[wells["treatment"] == t, "dF"].to_numpy() for t in S.ORDER}
say("Change from before to after in each treatment (mean of the wells with 95% CI; a description, not a test)")
for t, v in groups.items():
    half = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v))
    say(f"  {t:12s} {v.mean():8.1f} counts  (95% CI {v.mean() - half:.1f} to {v.mean() + half:.1f}; "
        f"SD {v.std(ddof=1):.1f}; n = {len(v)} wells)")

probes = [t for t in S.ORDER if t != S.CONTROL]
d = stats.dunnett(*[groups[t] for t in probes], control=groups[S.CONTROL], random_state=0)
ci = d.confidence_interval()
say(f"Test 1. Did each probe concentration change the beads more than buffer alone? "
    f"(Dunnett's test, corrected for {len(probes)} comparisons)")
for i, t in enumerate(probes):
    say(f"  {t:12s} {groups[t].mean() - groups[S.CONTROL].mean():8.1f} counts more than buffer "
        f"(95% CI {ci.low[i]:.1f} to {ci.high[i]:.1f}), p = {fmt_p(d.pvalue[i])}")

probe_wells = wells[wells["treatment"] != S.CONTROL]
lr = stats.linregress(np.log2(probe_wells["dose"].astype(float)), probe_wells["dF"])
half = stats.t.ppf(0.975, len(probe_wells) - 2) * lr.stderr
say("Test 2. Does the change grow with concentration? (linear regression on log2 concentration, "
    "probe wells only)")
say(f"  slope {lr.slope:.1f} counts per doubling of concentration (95% CI {lr.slope - half:.1f} to "
    f"{lr.slope + half:.1f}), R² = {lr.rvalue ** 2:.2f}, p = {fmt_p(lr.pvalue)}, n = {len(probe_wells)} wells")
say("  Caution: beads at the detector maximum have their signal capped (pct_saturated_after), which flattens "
    "this slope. A flat slope does not show that binding is independent of concentration.")

# ---- 6. representative images: typical well, then typical image (by rule, not by eye) ----------
reps = []
for t in S.ORDER:
    w = wells[wells["treatment"] == t]
    well = w.loc[(w["dF"] - w["dF"].median()).abs().idxmin(), "well"]
    for tp in ("before", "after"):
        cand = img[(img["well"] == well) & (img["timepoint"] == tp)]
        target = w.loc[w["well"] == well, f"F_{tp}"].iat[0]
        r = cand.loc[(cand["F"] - target).abs().idxmin()]
        reps.append({"treatment": t, "timepoint": tp, "well": r["well_name"], "position": r["position"],
                     "file": r["file"], "image_mean_F": round(r["F"], 1), "well_mean_F": round(target, 1)})
pd.DataFrame(reps).to_csv(OUT / "representative_images.csv", index=False)

# ---- 7. save --------------------------------------------------------------------------------------
say(f"\nSoftware: Python {platform.python_version()}, numpy {np.__version__}, "
    f"pandas {pd.__version__}, scipy {scipy.__version__}")
(OUT / "stats_report.txt").write_text("\n".join(report), encoding="utf-8")
print(f"\nAnalysis done. Results in {OUT}")
