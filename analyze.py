"""
analyze.py: turns the Fiji macro's bead measurements into per-well before/after results and
statistics. Images are labelled from their file names (convention in README.md), so new images are
included without changing the code. Settings are in settings.py; figures are drawn by make_figures.py.

Each well's after-treatment beads are compared with the same well's before-treatment beads. The
two timepoints show different fields of view, so bead populations are compared, not individual beads.

Run from the project folder, after the Fiji macro:   python3 analyze.py

Writes to results/analysis:
  file_labels.csv            how every file name was read and which images were used (check this first)
  bead_table.csv             every bead used, labelled (a shared before image appears once per treatment)
  image_summary.csv          one row per image and treatment
  well_summary.csv           one row per well and treatment (the replicate)
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
MAX = S.MAX_IMAGES_PER_WELL
BUFFER, NEGCTRL, PROBE = S.KINDS["buffer"], S.KINDS["negctrl"], S.KINDS["probe"]
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


def treatments(word):
    """Labels for a treatment word of the file names: 'probe-1to400' -> ['Probe 1:400']. A before image shared
    by several dilutions names them all: 'probe-1to3333-5000-10000' -> Probe 1:3333, 1:5000 and 1:10000."""
    kind, _, dilutions = word.partition("-1to")
    return [f"{S.KINDS[kind]} 1:{d}" for d in dilutions.split("-")] if dilutions else [S.KINDS[kind]]


def display_order(label):
    """Sort key: the kinds in their settings.py order, each from most to least diluted."""
    kind, _, dilution = label.partition(" 1:")
    return list(S.KINDS.values()).index(kind), -int(dilution or 0)


# ---- 1. read the file names and choose the images ------------------------------------------------
# after_probe-1to400_W01_2b = after treatment, probe 1:400, well 1, position 2, second field at that
# position (b). A well is identified by its number and treatment.
NAME = re.compile(r"(before|after)_([a-z0-9-]+)_W(\d+)_(\d+)([a-z]?)")
skip = {f: "background image, not a bead field" for f in log.index if Path(f).stem.endswith("_background")}
skip.update(S.EXCLUDE)
beads = beads[~beads["file"].isin(skip)]
names = beads["file"].unique()
files = pd.DataFrame([NAME.fullmatch(Path(f).stem).groups() for f in names], index=pd.Index(names, name="file"),
                     columns=["timepoint", "label", "well", "position", "field"])
files[["well", "position"]] = files[["well", "position"]].astype(int)
files["n_beads"] = beads.groupby("file").size()
files["status"] = "used"

# at most MAX images per well, timepoint and treatment: most beads first, then the originally named
# field of a position before a second field ("" sorts before "b"), then the lowest position
ranked = files.sort_values(["n_beads", "field", "position"], ascending=[False, True, True])
over = ranked.groupby(["timepoint", "label", "well"]).cumcount() >= MAX
files.loc[ranked.index[over], "status"] = f"more than {MAX} images in the well; fewest beads"
files.reset_index().to_csv(OUT / "file_labels.csv", index=False)
no_beads = {f: "no beads passed the size, shape and focus checks" for f in log.index[log["beads_kept"] == 0]}
not_used = {**no_beads, **skip, **files.loc[files["status"] != "used", "status"]}
say("Images not used:\n" + "\n".join(f"  {f}: {why}" for f, why in sorted(not_used.items())))

used = files[files["status"] == "used"].copy()
used["well_name"] = "W" + used["well"].astype(str)
used["image"] = used["well_name"] + "." + used["position"].astype(str) + used["field"]
# a shared before image is the baseline for each of its treatments; a well is compared only if it has
# images at both timepoints
used["treatment"] = used["label"].map(treatments)
used = used.explode("treatment")
both = used.groupby(["well_name", "treatment"])["timepoint"].transform("nunique") == 2
one_tp = (used.loc[~both, "well_name"] + " " + used.loc[~both, "treatment"]).unique()
say("Wells not compared, with images at one timepoint only: " + ("; ".join(sorted(one_tp)) or "none"))
used = used[both]
n_wells = used[used["timepoint"] == "before"].groupby(["well", "label"]).ngroups   # a shared before image = 1 well
ORDER = sorted(used["treatment"].unique(), key=display_order)
n_img = used.groupby(["well_name", "treatment", "timepoint"]).size()
say(f"Wells with fewer than {MAX} images: "
    + ("; ".join(f"{w} {t} {tp} ({n})" for (w, t, tp), n in n_img[n_img < MAX].items()) or "none"))
images = used[~used.index.duplicated()]                  # one row per image
n = images.assign(oof=images.index.map(log["out_of_focus"])).groupby("timepoint").agg(
    images=("n_beads", "size"), beads=("n_beads", "sum"), oof=("oof", "sum")).loc[["before", "after"]]
n["found"] = n["beads"] + n["oof"]                       # beads found before the focus checks

# ---- 2. per-bead measures ------------------------------------------------------------------------
beads = beads.merge(used[["timepoint", "treatment", "well", "well_name", "position", "image"]]
                    .reset_index(), on="file")
beads["F"] = beads["ring_mean"] - beads["bg_mean"]           # counts above local background
beads["SNR"] = beads["F"] / beads["bg_sd"]
beads["saturated"] = beads["disc_max"] >= S.SATURATION
beads.to_csv(OUT / "bead_table.csv", index=False)

# ---- 3. images, then wells (the replicate) --------------------------------------------------------
keys = ["treatment", "well", "well_name", "timepoint"]
img = beads.groupby(keys + ["image", "position"]).agg(
    file=("file", "first"), n_beads=("F", "size"), F=("F", "mean"), SNR=("SNR", "mean"), bg=("bg_mean", "mean"),
    pct_saturated=("saturated", "mean")).reset_index()
img = img.sort_values("treatment", key=lambda s: s.map(ORDER.index), kind="stable")   # treatment order, not A-Z
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

say(f"Well values compared: {len(wells)} (from {n_wells} wells); images before/after: "
    f"{n.images.before}/{n.images.after}; beads before/after: {n.beads.before}/{n.beads.after}")
say("Out-of-focus beads left out by the Fiji macro (transmitted-light focus checks): " + "; ".join(
    f"{tp} {r.oof} of {r.found} ({100 * r.oof / r.found:.0f}%)" for tp, r in n.iterrows()))

# ---- 4. treatment summary ----------------------------------------------------------------------------
rows = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    row = {"treatment": t, "n_wells": len(w)}
    for k in ["F_before", "F_after", "dF", "SNR_before", "SNR_after", "bg_before", "bg_after", "pct_saturated_after"]:
        row.update(zip([f"{k}_mean", f"{k}_sd", f"{k}_ci95_low", f"{k}_ci95_high"], mean_ci(w[k])))
    rows.append(row)
summary = pd.DataFrame(rows)
summary.to_csv(OUT / "treatment_summary.csv", index=False)
say("\nSignal = ring mean minus local background (counts).")
say(summary[["treatment", "n_wells", "F_before_mean", "F_after_mean", "dF_mean", "SNR_before_mean",
             "SNR_after_mean", "bg_after_mean", "pct_saturated_after_mean"]].round(1).to_string(index=False))

# ---- 5. statistics on well values ----------------------------------------------------------------------
# The well is the replicate; outcome = each well's change in bead fluorescence (dF). Three tests, each
# answering one question of the study (reasons in README.md), plus the mean change with 95% CI:
#   Test 1  Dunnett's test, each probe dilution vs buffer (did the probe do more than buffer?)
#   Test 2  Welch's t-test, probe vs negative control at the same dilution (is the binding specific?)
#   Test 3  Spearman rank correlation over all probe dilutions (does binding grow with less dilution?)
say("\nStatistics: well values (the replicate); outcome = each well's change from its own before images.")
say("\n=== Bead fluorescence (change in counts above background) ===")
say("Change from before to after in each treatment (mean of the wells with 95% CI; a description, not a test)")
for r in summary.itertuples():
    say(f"  {r.treatment:24s} {r.dF_mean:8.1f} counts  (95% CI {r.dF_ci95_low:.1f} to {r.dF_ci95_high:.1f}; "
        f"SD {r.dF_sd:.1f}; n = {r.n_wells} wells)")
dF = {t: wells.loc[wells["treatment"] == t, "dF"].to_numpy() for t in ORDER}
probes = [t for t in ORDER if t.startswith(PROBE)]
test = stats.dunnett(*[dF[t] for t in probes], control=dF[BUFFER], random_state=0)
ci = test.confidence_interval()
say(f"Test 1. Did each probe dilution change the beads more than buffer alone? "
    f"(Dunnett's test, corrected for {len(probes)} comparisons)")
for i, t in enumerate(probes):
    say(f"  {t:14s} {dF[t].mean() - dF[BUFFER].mean():+8.1f} counts vs buffer "
        f"(95% CI {ci.low[i]:.1f} to {ci.high[i]:.1f}), p = {fmt_p(test.pvalue[i])}")
say("Test 2. Does the probe bind more than the negative control at the same dilution? (Welch's t-test)")
for neg in [t for t in ORDER if t.startswith(NEGCTRL)]:
    probe = PROBE + neg.removeprefix(NEGCTRL)               # "Negative control 1:3333" -> "Probe 1:3333"
    if probe in dF:
        test = stats.ttest_ind(dF[probe], dF[neg], equal_var=False)
        ci = test.confidence_interval()
        say(f"  {probe:14s} {dF[probe].mean() - dF[neg].mean():+8.1f} counts vs {neg.lower()} "
            f"(95% CI {ci.low:.1f} to {ci.high:.1f}), p = {fmt_p(test.pvalue)}, "
            f"n = {len(dF[probe])} and {len(dF[neg])} wells")
probe_wells = wells[wells["treatment"].astype(str).str.startswith(PROBE)]
dilution = probe_wells["treatment"].astype(str).str.extract(r"1:(\d+)")[0].astype(float)
rank = stats.spearmanr(-dilution, probe_wells["dF"])         # positive rho = more probe, more signal
say(f"Test 3. Does the change grow as the probe is less diluted, over all {dilution.nunique()} "
    f"dilutions from 1:{dilution.max():.0f} to 1:{dilution.min():.0f}? (Spearman rank correlation)")
say(f"  rho = {rank.statistic:.2f}, p = {fmt_p(rank.pvalue)}, n = {len(probe_wells)} well values")
say("  Caution: beads at the detector maximum have their signal capped (pct_saturated_after), and a well "
    "whose before images are shared counts once for each of its dilutions.")

# ---- 6. representative images, chosen by rule: the typical well, then its typical image -------------------
reps = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    i = (w["dF"] - w["dF"].median()).abs().idxmin()          # well whose change is closest to the median
    for tp in ("before", "after"):
        cand = img[(img["treatment"] == t) & (img["well_name"] == w.at[i, "well_name"]) & (img["timepoint"] == tp)]
        target = w.at[i, f"F_{tp}"]
        r = cand.loc[(cand["F"] - target).abs().idxmin()]    # image closest to the well mean
        reps.append({"treatment": t, "timepoint": tp, "well": r["well_name"], "position": r["image"].split(".")[1],
                     "file": r["file"], "image_mean_F": round(r["F"], 1), "well_mean_F": round(target, 1)})
pd.DataFrame(reps).to_csv(OUT / "representative_images.csv", index=False)

say(f"\nSoftware: Python {platform.python_version()}, numpy {np.__version__}, "
    f"pandas {pd.__version__}, scipy {scipy.__version__}")
(OUT / "stats_report.txt").write_text("\n".join(report), encoding="utf-8")
print(f"\nAnalysis done. Results in {OUT}")
