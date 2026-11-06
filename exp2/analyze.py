"""
analyze.py for exp2 (an earlier run with controls, annexin-V and the probe at 1:3333 and 1:1000, and a later run
with more 1:1000 wells): turns the Fiji macro's bead measurements into per-well before/after results and
statistics. Images are labelled from their file names (convention in README.md), so new images are included
without changing the code. Settings are in settings.py next to this file; figures are drawn by make_figures.py.

Each well's after-treatment beads are compared with the same well's before-treatment beads. The
two timepoints show different fields of view, so bead populations are compared, not individual beads.

Run after the Fiji macro has saved its results to exp2/results:
  python exp2/analyze.py

Writes to exp2/results/analysis:
  file_labels.csv            how every file name was read and which images were used (check this first)
  bead_table.csv             every bead used, labelled
  image_summary.csv          one row per image and treatment
  well_summary.csv           one row per well and treatment (the replicate)
  treatment_summary.csv      mean, SD and 95% CI per treatment
  representative_images.csv  typical before/after image per treatment, for fig0
  before_after_wells.csv     the wells in each bar of the before/after chart (fig2)
  figure_tests.csv           the comparisons marked on fig2
  stats_report.txt           the printed report, including the tests
"""
import itertools
import platform
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats

import settings as S                                             # exp2/settings.py, next to this file

FOLDER = Path(__file__).resolve().parent                         # exp2: its images, settings.py and results
RESULTS = FOLDER / "results"
OUT = RESULTS / "analysis"
if not (RESULTS / "bead_measurements.csv").exists():
    sys.exit(f"{RESULTS / 'bead_measurements.csv'} not found: run the Fiji macro first, saving to {RESULTS}")
OUT.mkdir(exist_ok=True)
beads = pd.read_csv(RESULTS / "bead_measurements.csv")
log = pd.read_csv(RESULTS / "segmentation_log.csv", index_col="file")
MAX = S.MAX_IMAGES_PER_WELL
report, warnings = [], []


def say(msg=""):
    print(msg)
    report.append(msg)


def warn(msg):
    """Something left out rather than stopping the run: reported, and counted at the end."""
    warnings.append(msg)
    say(f"WARNING: {msg}")


def fmt_p(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


def mean_ci(v):
    """Mean, SD and 95% confidence interval (t distribution) of a set of well values."""
    m, sd, n = v.mean(), v.std(), len(v)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return m, sd, m - half, m + half


def tidy(file):
    """A file name as it is read: lower case, without spaces, and repeated underscores as one, so
    'before__1to1000_W10_2.oir' and 'after_ Mposctrl_1to1000_W9_3 (400HV).oir' read like the others."""
    return re.sub(r"_+", "_", Path(file).stem.lower().replace(" ", ""))


def treatment_of(word):
    """The treatment name for a treatment word of the file names, from settings.GROUPS ('annexin' -> 'Annexin-V').
    None = a word set to None (not analysed); an unknown word raises KeyError."""
    return S.GROUPS[word]


def display_order(name):
    """Sort key: the treatments in their settings.GROUPS order."""
    return list(S.GROUPS.values()).index(name)


# ---- 1. read the file names and choose the images ------------------------------------------------
# after_annexin_W7_2 = after treatment, annexin-V, well 7, position 2; a second field at that position ends in
# b (W7_2b). A well is identified by its number and treatment. A name may end with a repeat save of the
# position (_0001) and a note in brackets ("(400HV)"); both are kept in the field, so every image stays distinct.
NAME = re.compile(r"(before|after)_(.+?)_w(\d+)_(\d+)([a-z]?)(?:_(\d{4}))?(?:\((.*)\))?")
skip = {f: "background image, not a bead field" for f in log.index if tidy(f).endswith("background")}
skip.update(S.EXCLUDE)
beads = beads[~beads["file"].isin(skip)]
rows, unread = [], {}             # unread: names that can't be read, left out and listed with the reason
for f in beads["file"].unique():
    m = NAME.fullmatch(tidy(f))
    if not m:
        unread[f] = "name not read as before/after_treatment_W(well)_(position)"
        continue
    timepoint, label, well, position, letter, save, note = m.groups()
    try:
        name = treatment_of(label)
    except KeyError:
        unread[f] = f"treatment '{label}' is not in GROUPS in {FOLDER / 'settings.py'}"
        continue
    rows.append({"file": f, "timepoint": timepoint, "label": label, "treatment": name or "",
                 "well": int(well), "position": int(position), "field": letter + (f"({note})" if note else ""),
                 "save": save or "", "status": "used" if name else f"'{label}' is set to None in GROUPS"})
files = pd.DataFrame(rows).set_index("file")
files["n_beads"] = beads.groupby("file").size()

# a position saved more than once (_0001, _0002, ...): the same field again if most beads of the later save lie
# within 2 µm of a bead of the earlier save; then only the latest save is used. Otherwise each save is a field.
xy = beads[["x_px", "y_px"]].mul(beads["file"].map(log["pixel_um"]), axis=0).groupby(beads["file"])
saved_twice = []
for _, saves in files[files["status"] == "used"].groupby(["timepoint", "label", "well", "position", "field"]):
    for earlier, later in itertools.pairwise(saves.sort_values("save").index):
        a, b = xy.get_group(earlier).to_numpy(), xy.get_group(later).to_numpy()
        same = (np.sqrt(((b[:, None] - a[None]) ** 2).sum(axis=2)).min(axis=1) < 2).mean() > 0.5
        if same:
            files.loc[earlier, "status"] = f"same field saved again as {later}, which is used"
        saved_twice.append(f"  {later}: {'the same field as' if same else 'a different field from'} {earlier}")
files["field"] = files["field"] + np.where(files["save"] != "", "_" + files["save"], "")
files = files.drop(columns="save")

# at most MAX images per well, timepoint and treatment (None = no limit): most beads first, then the originally
# named field of a position before a second field ("" sorts before "b"), then the lowest position
if MAX:
    ranked = files[files["status"] == "used"].sort_values(["n_beads", "field", "position"],
                                                          ascending=[False, True, True])
    over = ranked.groupby(["timepoint", "treatment", "well"]).cumcount() >= MAX
    files.loc[ranked.index[over], "status"] = f"more than {MAX} images in the well; fewest beads"
files.reset_index().to_csv(OUT / "file_labels.csv", index=False)
no_beads = {f: "no beads passed the size, shape and focus checks" for f in log.index[log["beads_kept"] == 0]}
not_used = {**no_beads, **skip, **unread, **files.loc[files["status"] != "used", "status"]}
say("Images not used:\n" + "\n".join(f"  {f}: {why}" for f, why in sorted(not_used.items())))
if unread:
    warn(f"{len(unread)} file name(s) couldn't be read, so those images are left out (listed above; rename them, "
         f"or add the treatment word to GROUPS in {FOLDER / 'settings.py'})")
if missing := sorted(set(S.EXCLUDE) - set(log.index)):
    say("Files listed in EXCLUDE but not found (check the names): " + "; ".join(missing))
if saved_twice:
    say("Positions saved more than once (same field: only the latest save is used; different field: both used):\n"
        + "\n".join(sorted(saved_twice)))

used = files[files["status"] == "used"].copy()
used["well_name"] = "W" + used["well"].astype(str)
used["image"] = used["well_name"] + "." + used["position"].astype(str) + used["field"]
# a well is compared only if it has images at both timepoints
both = used.groupby(["well_name", "treatment"])["timepoint"].transform("nunique") == 2
one_tp = (used.loc[~both, "well_name"] + " " + used.loc[~both, "treatment"]).unique()
say("Wells not compared, with images at one timepoint only: " + ("; ".join(sorted(one_tp)) or "none"))
used = used[both]
n_wells = used.groupby(["well", "treatment"]).ngroups
ORDER = sorted(used["treatment"].unique(), key=display_order)
n_img = used.groupby(["well_name", "treatment", "timepoint"]).size()
if MAX:
    say(f"Wells with fewer than {MAX} images: "
        + ("; ".join(f"{w} {t} {tp} ({n})" for (w, t, tp), n in n_img[n_img < MAX].items()) or "none"))
n = used.assign(oof=used.index.map(log["out_of_focus"])).groupby("timepoint").agg(
    images=("n_beads", "size"), beads=("n_beads", "sum"), oof=("oof", "sum")).loc[["before", "after"]]
n["found"] = n["beads"] + n["oof"]                       # beads found before the focus checks

# ---- 2. per-bead measures ------------------------------------------------------------------------
beads = beads.merge(used[["timepoint", "treatment", "well", "well_name", "position", "image"]]
                    .reset_index(), on="file")
beads["F"] = beads["ring_mean"] - beads["bg_mean"]           # counts above local background
beads["SNR"] = beads["F"] / beads["bg_sd"]
beads["saturated"] = beads["disc_max"] >= S.SATURATION
# a positive bead is brighter than nearly all untreated beads: above the mean + 3 SD of the before-treatment beads
before = beads[beads["timepoint"] == "before"]
cutoff = before["F"].mean() + 3 * before["F"].std()
beads["positive"] = beads["F"] > cutoff
beads.to_csv(OUT / "bead_table.csv", index=False)

# ---- 3. images, then wells (the replicate) --------------------------------------------------------
keys = ["treatment", "well", "well_name", "timepoint"]
img = beads.groupby(keys + ["image", "position", "file"]).agg(   # file too: two runs can image the same position
    n_beads=("F", "size"), F=("F", "mean"), SNR=("SNR", "mean"), bg=("bg_mean", "mean"),
    pct_saturated=("saturated", "mean"), pct_positive=("positive", "mean")).reset_index()
img = img.sort_values("treatment", key=lambda s: s.map(ORDER.index), kind="stable")   # treatment order, not A-Z
img[["pct_saturated", "pct_positive"]] *= 100
img.to_csv(OUT / "image_summary.csv", index=False)

per_tp = img.groupby(keys)[["F", "SNR", "bg", "pct_saturated", "pct_positive", "n_beads"]].mean()
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
say(f"Positive bead: above {cutoff:.1f} counts (mean + 3 SD of the {len(before)} before-treatment beads)")

# ---- 4. treatment summary ----------------------------------------------------------------------------
rows = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    row = {"treatment": t, "n_wells": len(w)}
    for k in ["F_before", "F_after", "dF", "SNR_before", "SNR_after", "bg_before", "bg_after", "pct_saturated_after",
              "pct_positive_after"]:
        row.update(zip([f"{k}_mean", f"{k}_sd", f"{k}_ci95_low", f"{k}_ci95_high"], mean_ci(w[k])))
    rows.append(row)
summary = pd.DataFrame(rows)
summary.to_csv(OUT / "treatment_summary.csv", index=False)
say("\nSignal = ring mean minus local background (counts).")
say(summary[["treatment", "n_wells", "F_before_mean", "F_after_mean", "dF_mean", "SNR_before_mean",
             "SNR_after_mean", "bg_after_mean", "pct_saturated_after_mean", "pct_positive_after_mean"]]
    .round(1).to_string(index=False))

# ---- 5. change in each treatment --------------------------------------------------------------------------
# The well is the replicate; outcome = each well's change in bead fluorescence (dF). The tests are those marked on
# fig2 (section 6).
say("\nStatistics: well values (the replicate); outcome = each well's change from its own before images.")
say("\n=== Bead fluorescence (change in counts above background) ===")
say("Change from before to after in each treatment (mean of the wells with 95% CI; a description, not a test)")
WIDTH = max(24, *map(len, ORDER))                          # name column of the report
for r in summary.itertuples():
    say(f"  {r.treatment:{WIDTH}s} {r.dF_mean:8.1f} counts  " + (
        f"(95% CI {r.dF_ci95_low:.1f} to {r.dF_ci95_high:.1f}; SD {r.dF_sd:.1f}; n = {r.n_wells} wells)"
        if r.n_wells > 1 else "(1 well, so no SD or CI)"))

# ---- 6. fig2 (before/after): the comparisons marked on it ---------------------------------------------------
# Each comparison needs at least 2 wells per treatment: each treatment before vs after (paired t-test on its wells),
# and every other treatment's after-treatment fluorescence vs settings.COMPARE_TO's (Dunnett's test, which
# corrects for comparing several treatments with one)
in_bar, rows = {}, []             # in_bar: fig2 bar (a treatment) -> its wells; a treatment without wells is left out
for t in S.BEFORE_AFTER:
    if not (wells["treatment"] == t).any():
        warn(f"fig2: the '{t}' bar is left out: no wells compared")
        continue
    in_bar[t] = w = wells[wells["treatment"] == t]
    if len(w) >= 2:
        rows.append(["fig2", "paired t-test, before vs after", t, t, w["dF"].mean(),
                     stats.ttest_rel(w["F_after"], w["F_before"]).pvalue])
ref = S.COMPARE_TO
compared = [t for t in in_bar if t != ref and len(in_bar[t]) >= 2]
if ref in in_bar and len(in_bar[ref]) >= 2 and compared:
    test = stats.dunnett(*[in_bar[t]["F_after"] for t in compared], control=in_bar[ref]["F_after"], random_state=0)
    rows += [["fig2", "Dunnett's test, after vs after", ref, t, in_bar[t]["F_after"].mean()
              - in_bar[ref]["F_after"].mean(), p] for t, p in zip(compared, test.pvalue)]
columns = ["treatment", "well_name", "F_before", "F_after", "dF"]
(pd.concat(in_bar.values())[columns] if in_bar else pd.DataFrame(columns=columns)).to_csv(
    OUT / "before_after_wells.csv", index=False)
tests = pd.DataFrame(rows, columns=["figure", "test", "a", "b", "difference", "p"])
tests.to_csv(OUT / "figure_tests.csv", index=False)
say("\n=== Comparisons marked on fig2 ===")
say("Each treatment before vs after (paired t-test on its wells; change in counts)")
for t in S.BEFORE_AFTER:
    r = tests[tests["test"].str.startswith("paired") & (tests["a"] == t)]
    say(f"  {t:{WIDTH}s} " + (f"{r.difference.iloc[0]:+8.1f} counts, p = {fmt_p(r.p.iloc[0])}" if len(r) else
                              "not tested: 1 well" if t in in_bar else "left out: no wells"))
dunnett = tests[tests["test"].str.startswith("Dunnett")]
if len(dunnett):
    say(f"After treatment, each treatment vs {ref} (Dunnett's test, corrected for {len(dunnett)} comparisons)")
    for r in dunnett.itertuples():
        say(f"  {r.b} vs {r.a}: {r.difference:+.1f} counts, p = {fmt_p(r.p)}")
    for t in in_bar:
        if t != ref and len(in_bar[t]) < 2:
            say(f"  {t} vs {ref}: not tested: 1 well")
else:
    say(f"No comparisons with {ref}: they need at least 2 wells in it and in another treatment.")

# ---- 7. representative images, chosen by rule: the typical well, then its typical image -------------------
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
if warnings:
    print(f"\n{len(warnings)} warning(s): see the WARNING lines above (also in stats_report.txt)")
print(f"\nAnalysis done. Results in {OUT}")
