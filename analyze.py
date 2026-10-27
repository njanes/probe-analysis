"""
analyze.py: turns the Fiji macro's bead measurements into per-well before/after results and
statistics. Images are labelled from their file names (convention in README.md), so new images are
included without changing the code. Settings are in settings.py; figures are drawn by make_figures.py.

Each well's after-treatment beads are compared with the same well's before-treatment beads. The
two timepoints show different fields of view, so bead populations are compared, not individual beads.

Run from the project folder, after the Fiji macro:
  python3 analyze.py           the study in the project folder (settings.py, images, results)
  python3 analyze.py study2    a study in its own folder, with its own settings.py, images and results

Writes to results/analysis (in the study's folder):
  file_labels.csv            how every file name was read and which images were used (check this first)
  bead_table.csv             every bead used, labelled (a shared before image appears once per treatment)
  image_summary.csv          one row per image and treatment
  well_summary.csv           one row per well and treatment (the replicate)
  treatment_summary.csv      mean, SD and 95% CI per treatment
  representative_images.csv  typical before/after image per treatment, for fig0
  dilution_fit.csv           the curve fitted to the dilution-response, for fig1 (empty if not fitted)
  before_after_wells.csv     the wells in each bar of the before/after charts (fig2 and any others in settings.py)
  figure_tests.csv           the comparisons marked on the bar charts, the before/after charts and fig3
  stats_report.txt           the printed report, including the tests
"""
import itertools
import platform
import re
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import scipy
from scipy import optimize, stats

FOLDER = Path(sys.argv[1] if len(sys.argv) > 1 else ".")          # the study's folder
RESULTS = FOLDER / "results"
OUT = RESULTS / "analysis"
if not (FOLDER / "settings.py").exists():
    sys.exit(f"{FOLDER / 'settings.py'} not found")
if not (RESULTS / "bead_measurements.csv").exists():
    sys.exit(f"{RESULTS / 'bead_measurements.csv'} not found: run the Fiji macro first, saving to {RESULTS}")
S = SimpleNamespace(**runpy.run_path(str(FOLDER / "settings.py")))
OUT.mkdir(exist_ok=True)
beads = pd.read_csv(RESULTS / "bead_measurements.csv")
log = pd.read_csv(RESULTS / "segmentation_log.csv", index_col="file")
MAX = S.MAX_IMAGES_PER_WELL
others = []                       # well values of other studies, for the before/after charts (settings.OTHER_STUDIES)
for folder, words in S.OTHER_STUDIES.items():
    path = Path(folder) / "results" / "analysis" / "well_summary.csv"
    if not path.exists():
        sys.exit(f"{path} not found: analyse that study first (python analyze.py {folder})")
    other = pd.read_csv(path)[["treatment", "well_name", "F_before", "F_after"]]
    others.append(other.assign(treatment=other["treatment"] + ", " + words))
BUFFER, NEGCTRL, PROBE = "Buffer only", "Negative control", "Probe"   # the treatment names the tests look for
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


def tidy(file):
    """A file name as it is read: lower case, without spaces, and repeated underscores as one, so
    'before__1to1000_W10_2.oir' and 'after_ Mposctrl_1to1000_W9_3 (400HV).oir' read like the others."""
    return re.sub(r"_+", "_", Path(file).stem.lower().replace(" ", ""))


def treatments(word):
    """Treatment names for a treatment word of the file names, from settings.GROUPS: the word itself
    ('annexin' -> ['Annexin-V']), or a kind with its dilution ('probe-1to400' -> ['Probe 1:400']). A before
    image shared by several dilutions names them all: 'probe-1to3333-5000-10000' -> Probe 1:3333, 1:5000 and
    1:10000. None = a word set to None (not analysed); an unknown word raises KeyError."""
    if word in S.GROUPS:
        return None if S.GROUPS[word] is None else [S.GROUPS[word]]
    kind, _, dilutions = word.partition("-1to")
    if dilutions and S.GROUPS.get(kind):
        return [f"{S.GROUPS[kind]} 1:{d}" for d in dilutions.split("-")]
    raise KeyError(word)


def logistic(log_d, bottom, top, log_d50, hill):
    """4-parameter logistic dose-response, in terms of the dilution factor D (1:D):
    y = bottom + (top - bottom) / (1 + (D / D50)^hill), with log_d = log10(D) and log_d50 = log10(D50)."""
    return bottom + (top - bottom) / (1 + 10 ** ((log_d - log_d50) * hill))


BASES = list(dict.fromkeys(name.partition(" 1:")[0] for name in S.GROUPS.values() if name))


def display_order(name):
    """Sort key: the treatments in their settings.GROUPS order, a kind's dilutions from most to least diluted."""
    base, _, dilution = name.partition(" 1:")
    return BASES.index(base), -int(dilution or 0)


def chosen(setting):
    """The treatments a figure setting names (a kind alone, such as "Probe", names all its dilutions), in
    display order; None = every treatment."""
    return [t for t in ORDER if setting is None or t in setting or t.partition(" 1:")[0] in setting]


def at_same_dilution(neg):
    """The probe at a negative control's dilution: 'Negative control 1:3333' -> 'Probe 1:3333'."""
    return PROBE + neg.removeprefix(NEGCTRL)


# ---- 1. read the file names and choose the images ------------------------------------------------
# after_probe-1to400_W01_2b = after treatment, probe 1:400, well 1, position 2, second field at that
# position (b). A well is identified by its number and treatment. A name may end with a repeat save of the
# position (_0001) and a note in brackets ("(400HV)"); both are kept in the field, so every image stays distinct.
NAME = re.compile(r"(before|after)_(.+?)_w(\d+)_(\d+)([a-z]?)(?:_(\d{4}))?(?:\((.*)\))?")
skip = {f: "background image, not a bead field" for f in log.index if tidy(f).endswith("background")}
skip.update(S.EXCLUDE)
beads = beads[~beads["file"].isin(skip)]
rows, problems = [], []
for f in beads["file"].unique():
    m = NAME.fullmatch(tidy(f))
    if not m:
        problems.append(f"  {f}: not read as before/after_treatment_W(well)_(position); rename it, or add it "
                        f"to EXCLUDE in {FOLDER / 'settings.py'}")
        continue
    timepoint, label, well, position, letter, save, note = m.groups()
    try:
        names = treatments(label)
    except KeyError:
        problems.append(f"  {f}: treatment '{label}' is not in GROUPS in {FOLDER / 'settings.py'}")
        continue
    rows.append({"file": f, "timepoint": timepoint, "label": label, "treatment": "; ".join(names or []),
                 "well": int(well), "position": int(position), "field": letter + (f"({note})" if note else ""),
                 "save": save or "", "status": "used" if names else f"'{label}' is set to None in GROUPS"})
if problems:
    sys.exit("File names that can't be read:\n" + "\n".join(problems))
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
not_used = {**no_beads, **skip, **files.loc[files["status"] != "used", "status"]}
say("Images not used:\n" + "\n".join(f"  {f}: {why}" for f, why in sorted(not_used.items())))
if missing := sorted(set(S.EXCLUDE) - set(log.index)):
    say("Files listed in EXCLUDE but not found (check the names): " + "; ".join(missing))
if saved_twice:
    say("Positions saved more than once (same field: only the latest save is used; different field: both used):\n"
        + "\n".join(sorted(saved_twice)))

used = files[files["status"] == "used"].copy()
used["well_name"] = "W" + used["well"].astype(str)
used["image"] = used["well_name"] + "." + used["position"].astype(str) + used["field"]
# a shared before image is the baseline for each of its treatments; a well is compared only if it has
# images at both timepoints
used["treatments"] = used["treatment"]
used["treatment"] = used["treatment"].str.split("; ")
used = used.explode("treatment")
both = used.groupby(["well_name", "treatment"])["timepoint"].transform("nunique") == 2
one_tp = (used.loc[~both, "well_name"] + " " + used.loc[~both, "treatment"]).unique()
say("Wells not compared, with images at one timepoint only: " + ("; ".join(sorted(one_tp)) or "none"))
used = used[both]
n_wells = used[used["timepoint"] == "before"].groupby(["well", "treatments"]).ngroups   # a shared before image = 1 well
ORDER = sorted(used["treatment"].unique(), key=display_order)
n_img = used.groupby(["well_name", "treatment", "timepoint"]).size()
if MAX:
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
# a positive bead is brighter than nearly all untreated beads: above the mean + 3 SD of the before-treatment
# beads (a shared before image counted once)
before = beads[beads["timepoint"] == "before"].drop_duplicates(["file", "bead"])
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
# dilution-response (fig1): every probe dilution, with each well's change as a % of the strongest of their
# mean changes
in_response = wells["treatment"].astype(str).str.startswith(PROBE + " 1:")
response_means = wells[in_response].groupby("treatment", observed=True)["dF"].mean()
wells["dF_pct"] = 100 * wells["dF"] / response_means.max()
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

# ---- 5. statistics on well values ----------------------------------------------------------------------
# The well is the replicate; outcome = each well's change in bead fluorescence (dF). Three tests, each
# answering one question of the study (reasons in README.md), plus the mean change with 95% CI. Each runs
# when the study has the treatments it needs:
#   Test 1  Dunnett's test, each probe dilution vs buffer (did the probe do more than buffer?)
#   Test 2  Welch's t-test, probe vs negative control at the same dilution (is the binding specific?)
#   Test 3  Spearman rank correlation over all probe dilutions (does binding grow with less dilution?)
say("\nStatistics: well values (the replicate); outcome = each well's change from its own before images.")
say("\n=== Bead fluorescence (change in counts above background) ===")
say("Change from before to after in each treatment (mean of the wells with 95% CI; a description, not a test)")
WIDTH = max(24, *map(len, ORDER))                          # name column of the report
for r in summary.itertuples():
    say(f"  {r.treatment:{WIDTH}s} {r.dF_mean:8.1f} counts  " + (
        f"(95% CI {r.dF_ci95_low:.1f} to {r.dF_ci95_high:.1f}; SD {r.dF_sd:.1f}; n = {r.n_wells} wells)"
        if r.n_wells > 1 else "(1 well, so no SD or CI)"))
dF = {t: wells.loc[wells["treatment"] == t, "dF"].to_numpy() for t in ORDER}
probes = [t for t in ORDER if t.startswith(PROBE + " 1:")]
if BUFFER in dF and probes:
    test = stats.dunnett(*[dF[t] for t in probes], control=dF[BUFFER], random_state=0)
    ci = test.confidence_interval()
    say(f"Test 1. Did each probe dilution change the beads more than buffer alone? "
        f"(Dunnett's test, corrected for {len(probes)} comparisons)")
    for i, t in enumerate(probes):
        say(f"  {t:14s} {dF[t].mean() - dF[BUFFER].mean():+8.1f} counts vs buffer "
            f"(95% CI {ci.low[i]:.1f} to {ci.high[i]:.1f}), p = {fmt_p(test.pvalue[i])}")
else:
    say(f"Test 1 (each probe dilution vs buffer) not run: it needs a '{BUFFER}' treatment and probe dilutions.")
pairs = [(neg, at_same_dilution(neg)) for neg in ORDER
         if neg.startswith(NEGCTRL + " 1:") and min(len(dF[neg]), len(dF.get(at_same_dilution(neg), []))) >= 2]
if pairs:
    say("Test 2. Does the probe bind more than the negative control at the same dilution? (Welch's t-test)")
    for neg, probe in pairs:
        test = stats.ttest_ind(dF[probe], dF[neg], equal_var=False)
        ci = test.confidence_interval()
        say(f"  {probe:14s} {dF[probe].mean() - dF[neg].mean():+8.1f} counts vs {neg.lower()} "
            f"(95% CI {ci.low:.1f} to {ci.high:.1f}), p = {fmt_p(test.pvalue)}, "
            f"n = {len(dF[probe])} and {len(dF[neg])} wells")
else:
    say(f"Test 2 (probe vs negative control at the same dilution) not run: it needs '{NEGCTRL} 1:N' and "
        f"'{PROBE} 1:N' at the same dilution, with at least 2 wells each.")
probe_wells = wells[in_response]
dilution = probe_wells["treatment"].astype(str).str.extract(r"1:(\d+)")[0].astype(float)
if dilution.nunique() >= 3:
    rank = stats.spearmanr(-dilution, probe_wells["dF"])         # positive rho = more probe, more signal
    say(f"Test 3. Does the change grow as the probe is less diluted, over all {dilution.nunique()} "
        f"dilutions from 1:{dilution.max():.0f} to 1:{dilution.min():.0f}? (Spearman rank correlation)")
    say(f"  rho = {rank.statistic:.2f}, p = {fmt_p(rank.pvalue)}, n = {len(probe_wells)} well values")
    say("  Caution: beads at the detector maximum have their signal capped (pct_saturated_after), and a well "
        "whose before images are shared counts once for each of its dilutions.")
else:
    say(f"Test 3 (trend over the probe dilutions) not run: it needs at least 3 probe dilutions "
        f"({dilution.nunique()} here).")

# ---- 6. dilution-response curve (fig1), fitted to the well values (needs 4 dilutions for 4 parameters) ------
say("\n=== Dilution-response (fig1) ===")
log_d = np.log10(dilution).to_numpy()
y = probe_wells["dF_pct"].to_numpy()
if dilution.nunique() >= 4:
    (bottom, top, log_d50, hill), _ = optimize.curve_fit(logistic, log_d, y, p0=[0, 100, np.median(log_d), 1])
    r2 = 1 - ((y - logistic(log_d, bottom, top, log_d50, hill)) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    fit = [{"bottom": bottom, "top": top, "D50": 10 ** log_d50, "hill": hill, "r_squared": r2, "n_wells": len(y)}]
    say(f"% fluorescence = each well's change as a % of the mean change with {response_means.idxmax()}, "
        f"the strongest")
    say(f"4-parameter logistic fit over {len(y)} well values: y = {bottom:.1f} + {top - bottom:.1f} / "
        f"(1 + (D / {10 ** log_d50:.0f})^{hill:.2f}), D = dilution factor (1:D); R² = {r2:.2f}; "
        f"midpoint at 1:{10 ** log_d50:.0f}")
else:
    fit = []
    say(f"Not fitted, so no fig1: the curve needs at least 4 probe dilutions ({dilution.nunique()} here).")
pd.DataFrame(fit, columns=["bottom", "top", "D50", "hill", "r_squared", "n_wells"]).to_csv(
    OUT / "dilution_fit.csv", index=False)

# ---- 7. before/after bar charts (settings.BEFORE_AFTER) and fig3: the comparisons marked on them -------------
# A before/after bar pools the wells of the treatments listed for it, which can include another study's
# (settings.OTHER_STUDIES). Each comparison needs at least 2 wells per bar or treatment:
#   before/after: each bar before vs after (paired t-test on its wells), the probe's after-treatment
#                 fluorescence vs the negative control's at the same dilution (Welch's t-test), and, in a chart
#                 listed in settings.COMPARE_TO, every other bar's after-treatment fluorescence vs that bar's
#                 (Dunnett's test, which corrects for comparing several bars with one)
#   fig3:         the dilutions' % of positive beads compared pairwise (one-way ANOVA, then Tukey's test)
pool = pd.concat([wells.astype({"treatment": str}), *others])
pool["dF"] = pool["F_after"] - pool["F_before"]
bars, rows = [], []
for fig, figure_bars in S.BEFORE_AFTER.items():
    tag = fig.split("_")[0]                                       # "fig2", as in figure_tests.csv
    in_bar = {}
    for bar, names in figure_bars.items():
        if missing := sorted(set(names) - set(pool["treatment"])):
            sys.exit(f"BEFORE_AFTER in {FOLDER / 'settings.py'}: no wells compared for {'; '.join(missing)}")
        in_bar[bar] = w = pool[pool["treatment"].isin(names)]
        bars.append(w.assign(figure=fig, bar=bar))
        if len(w) >= 2:
            rows.append([tag, "paired t-test, before vs after", bar, bar, w["dF"].mean(),
                         stats.ttest_rel(w["F_after"], w["F_before"]).pvalue])
    for neg in figure_bars:
        probe = at_same_dilution(neg)
        if neg.startswith(NEGCTRL + " 1:") and probe in figure_bars and min(len(in_bar[neg]), len(in_bar[probe])) >= 2:
            a, b = in_bar[neg]["F_after"], in_bar[probe]["F_after"]
            rows.append([tag, "Welch t-test, after vs after", neg, probe, b.mean() - a.mean(),
                         stats.ttest_ind(b, a, equal_var=False).pvalue])
    if ref := S.COMPARE_TO.get(fig):                              # every other bar vs one bar, after treatment
        if ref not in figure_bars:
            sys.exit(f"COMPARE_TO in {FOLDER / 'settings.py'}: '{ref}' is not a bar of {fig}")
        compared = [bar for bar in figure_bars if bar != ref and len(in_bar[bar]) >= 2]
        if len(in_bar[ref]) >= 2 and compared:
            test = stats.dunnett(*[in_bar[bar]["F_after"] for bar in compared], control=in_bar[ref]["F_after"],
                                 random_state=0)
            rows += [[tag, "Dunnett's test, after vs after", ref, bar, in_bar[bar]["F_after"].mean()
                      - in_bar[ref]["F_after"].mean(), p] for bar, p in zip(compared, test.pvalue)]
if bars:
    pd.concat(bars)[["figure", "bar", "treatment", "well_name", "F_before", "F_after", "dF"]].to_csv(
        OUT / "before_after_wells.csv", index=False)
groups = chosen(S.POSITIVE_BEADS)
v = [wells.loc[wells["treatment"] == t, "pct_positive_after"].to_numpy() for t in groups]
tukey = len(groups) >= 2 and min(map(len, v)) >= 2
if tukey:
    p = stats.tukey_hsd(*v).pvalue
    rows += [["fig3", "Tukey, % positive after", groups[i], groups[j], v[j].mean() - v[i].mean(), p[i, j]]
             for i, j in itertools.combinations(range(len(groups)), 2)]
tests = pd.DataFrame(rows, columns=["figure", "test", "a", "b", "difference", "p"])
tests.to_csv(OUT / "figure_tests.csv", index=False)
say("\n=== Comparisons marked on the bar charts ===")
for fig, figure_bars in S.BEFORE_AFTER.items():
    tag, width = fig.split("_")[0], max(WIDTH, *map(len, figure_bars))
    shown = tests[tests["figure"] == tag]
    say(f"Figure {tag[3:]}: each treatment before vs after (paired t-test on its wells; change in counts)")
    for bar, names in figure_bars.items():                       # what each bar holds, if not just its own name
        if names != [bar]:
            n = {name: int((pool["treatment"] == name).sum()) for name in names}
            say(f"  {bar} holds " + "; ".join(f"{name} ({k} well{'s' * (k != 1)})" for name, k in n.items()))
    for bar in figure_bars:
        r = shown[shown["test"].str.startswith("paired") & (shown["a"] == bar)]
        say(f"  {bar:{width}s} " + (f"{r.difference.iloc[0]:+8.1f} counts, p = {fmt_p(r.p.iloc[0])}" if len(r) else
                                   "not tested: 1 well"))
    welch = shown[shown["test"].str.startswith("Welch")]
    if len(welch):
        say(f"Figure {tag[3:]}: after treatment, the probe vs the negative control at the same dilution "
            f"(Welch's t-test)")
    for r in welch.itertuples():
        say(f"  {r.b} vs {r.a}: {r.difference:+.1f} counts, p = {fmt_p(r.p)}")
    if ref := S.COMPARE_TO.get(fig):
        dunnett = shown[shown["test"].str.startswith("Dunnett")]
        say(f"Figure {tag[3:]}: after treatment, each treatment vs {ref} (Dunnett's test, corrected for "
            f"{len(dunnett)} comparisons)" if len(dunnett) else
            f"Figure {tag[3:]}: no comparisons with {ref}; they need at least 2 wells in it and in another bar")
        for r in dunnett.itertuples():
            say(f"  {r.b} vs {r.a}: {r.difference:+.1f} counts, p = {fmt_p(r.p)}")
if tukey:
    say(f"Figure 3: % of positive beads compared between dilutions (one-way ANOVA p = "
        f"{fmt_p(stats.f_oneway(*v).pvalue)}, then Tukey's test)")
    for r in tests[tests["figure"] == "fig3"].itertuples():
        say(f"  {r.b} vs {r.a}: {r.difference:+.1f} percentage points, p = {fmt_p(r.p)}")
elif groups:
    say("Figure 3: no comparisons; they need at least 2 treatments, each with at least 2 wells.")

# ---- 8. representative images, chosen by rule: the typical well, then its typical image -------------------
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
