"""
analyze.py: reads bead_measurements.csv from the Fiji macro and produces the
per-well before/after results and statistics. No figures (see make_figures.py).

Each well's after-treatment beads are compared with the SAME well's before-treatment
beads. Before and after were imaged on different days, so the fields of view differ;
the comparison is between the bead populations of a well, not individual beads.

Run from the project folder:   python3 analyze.py results
       ("results" = the macro's results folder, or the bead_measurements.csv inside it),
       then make_figures.py with the same path
Settings: settings.py

Writes to an "analysis" folder next to the CSV:
  file_labels.csv          how every file name was read (check this first)
  bead_table.csv           every bead, labelled
  image_summary.csv        one row per image
  well_summary.csv         one row per well (the replicate)
  treatment_summary.csv    mean, SD and 95% CI per treatment
  representative_images.csv  typical before/after image per treatment, for the figure
  stats_report.txt         all tests, in plain language
  analysis_info.json       values make_figures.py needs
"""
import json
import platform
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats
from scipy.spatial import cKDTree

import settings as S

warnings.filterwarnings("ignore", category=RuntimeWarning)   # e.g. identical values in a group

csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "bead_measurements.csv"
if csv_path.is_dir():                              # the Fiji results folder also works
    csv_path = csv_path / "bead_measurements.csv"
if not csv_path.is_file():
    sys.exit(f"Can't find {csv_path}\nGive the path to bead_measurements.csv or the folder it is in.")
out = csv_path.parent / "analysis"
out.mkdir(exist_ok=True)
report = []


def say(msg=""):
    print(msg)
    report.append(msg)


# ---- 1. read every file name ---------------------------------------------------------
beads = pd.read_csv(csv_path)
marks = "|".join(re.escape(m) for m in sorted(S.BEFORE_MARKS + S.AFTER_MARKS, key=len, reverse=True))
NAME = re.compile(r"[_-](?P<tp>" + marks + r")[._]?"
                  r"(?P<code>AV\d+|P\d+(?:\.\d+)?)?[._W]*(?P<well>\d+)[._](?P<pos>\d{1,2})"
                  r"(?:_(?P<rep>\d{4}))?$", re.I)
before_marks = [b.lower() for b in S.BEFORE_MARKS]
rows = []
for f in beads["file"].unique():
    m = NAME.search(Path(f).stem)
    if not m:
        rows.append({"file": f, "timepoint": None})
        continue
    rows.append({"file": f, "timepoint": "before" if m["tp"].lower() in before_marks else "after",
                 "code": m["code"], "well": int(m["well"]), "position": int(m["pos"]),
                 "repeat": int(m["rep"] or 0)})
labels = pd.DataFrame(rows)
bad = labels[labels["timepoint"].isna()]["file"].tolist()
labels = labels.dropna(subset=["timepoint"]).copy()
labels["well"] = labels["well"].astype(int)
labels["position"] = labels["position"].astype(int)

# treatment of each well: from its own file name, else from the other images of that well
known = labels.dropna(subset=["code"]).groupby("well")["code"].agg(lambda s: s.mode().iat[0])
labels["code"] = labels["code"].fillna(labels["well"].map(known))
overrides = {int(str(k).lstrip("Ww")): v for k, v in S.WELL_OVERRIDES.items()}
labels["code"] = labels.apply(lambda r: overrides.get(r["well"], r["code"]), axis=1)
labels["well_name"] = labels["well"].map(lambda w: f"W{w}")

say(f"Read {Path(csv_path.parent.name) / csv_path.name}")     # folder + file only, no personal path
if bad:
    say(f"WARNING: could not read {len(bad)} file name(s), skipped: {bad}")
say("Files per treatment code and timepoint:\n"
    + labels.groupby(["code", "timepoint"])["file"].nunique().unstack(fill_value=0).to_string())
no_code = labels[labels["code"].isna()]
if len(no_code):
    say(f"WARNING: no treatment known for well(s) {sorted(no_code['well_name'].unique())} "
        f"(no after images?); left out: {no_code['file'].tolist()}")
unknown = sorted(set(labels["code"].dropna()) - set(S.TREATMENTS))
if unknown:
    say(f"WARNING: codes not in settings.TREATMENTS, skipped: {unknown}")
labels = labels[labels["code"].isin(S.TREATMENTS)]
if "before" not in set(labels["timepoint"]):
    sys.exit("No before-treatment files recognised. Check BEFORE_MARKS in settings.py.")

# ---- 2. clean the file list ------------------------------------------------------------
labels["status"] = "used"
for part, why in S.EXCLUDE_FILES.items():
    hit = labels["file"].str.contains(part, regex=False)
    labels.loc[hit, "status"] = f"excluded: {why}"
if (labels["status"] != "used").any():
    ex = labels[labels["status"] != "used"]
    say(f"Excluded in settings.py: {ex['file'].tolist()}")

log_path = csv_path.parent / "segmentation_log.csv"
if log_path.exists():
    labels["pixel_um"] = labels["file"].map(pd.read_csv(log_path).set_index("file")["pixel_um"])
else:
    labels["pixel_um"] = np.nan
    say("Note: segmentation_log.csv not found next to the CSV, so image resolution was not checked.")
usual = labels["pixel_um"].mode().iat[0] if labels["pixel_um"].notna().any() else np.nan
labels["other_res"] = labels["pixel_um"].notna() & ((labels["pixel_um"] / usual - 1).abs() > S.PIXEL_TOLERANCE)
if labels["other_res"].any():
    files_ = labels.loc[labels["other_res"], "file"].tolist()
    if S.DROP_OTHER_RESOLUTION:
        labels.loc[labels["other_res"] & (labels["status"] == "used"), "status"] = "excluded: other resolution"
        say(f"Left out (different resolution): {files_}")
    else:
        say(f"Different resolution, kept (macro scales its pixel settings): {files_}")

# repeat saves: same field -> retake (keep one); different field -> keep as an extra image
pix = labels.set_index("file")["pixel_um"].fillna(usual if not np.isnan(usual) else 1.0)
pts = {f: g[["x_px", "y_px"]].to_numpy() * pix.get(f, 1.0) for f, g in beads.groupby("file")}


def same_field(a, b, tol=1.5):
    """True if two images show the same beads (positions in microns, allowing a stage shift)."""
    A, B = pts.get(a, np.empty((0, 2))), pts.get(b, np.empty((0, 2)))
    if len(A) < 3 or len(B) < 3:
        return None                                     # too few beads to tell
    d = (B[None, :, :] - A[:, None, :]).reshape(-1, 2)
    vals, counts = np.unique(np.round(d / 2.0), axis=0, return_counts=True)
    shift = vals[counts.argmax()] * 2.0
    shift = d[np.all(np.abs(d - shift) < 3, axis=1)].mean(axis=0)
    matches = (cKDTree(B).query(A + shift)[0] < tol).sum()
    return bool(matches >= 3 and matches / min(len(A), len(B)) >= 0.4)


labels["field"] = 0
labels["same_as"] = ""
used = labels["status"] == "used"
for (tp, well, pos), g in labels[used].groupby(["timepoint", "well", "position"]):
    if len(g) == 1:
        continue
    fields = []                                         # lists of files showing one field
    for f in g.sort_values("repeat")["file"]:
        for fld in fields:
            if same_field(f, fld[0]) is not False:      # same field, or can't tell: treat as retake
                fld.append(f)
                break
        else:
            fields.append([f])
    for k, fld in enumerate(fields):
        sub = labels[labels["file"].isin(fld)]
        order_ = sub.sort_values(["other_res", "repeat"], ascending=[True, S.DUPLICATES != "last"])
        keep = order_["file"].iat[0]
        labels.loc[labels["file"].isin(fld), "field"] = k
        for f in fld:
            if f != keep:
                labels.loc[labels["file"] == f, ["status", "same_as"]] = ["retake (same field), not used", keep]
retakes = labels[labels["status"].str.startswith("retake")]
if len(retakes):
    say("Retakes of the same field (one kept per field): "
        + "; ".join(f"{r.file} = {r.same_as}" for r in retakes.itertuples()))
extra = labels[(labels["status"] == "used") & (labels["field"] > 0)]
if len(extra):
    say(f"Repeat saves showing a DIFFERENT field, kept as extra images: {extra['file'].tolist()}")
# at most MAX_IMAGES_PER_WELL per well and timepoint: keep the best (never judged on fluorescence)
labels["n_beads"] = labels["file"].map(beads.groupby("file").size()).fillna(0).astype(int)
for (tp, well), g in labels[labels["status"] == "used"].groupby(["timepoint", "well"]):
    if len(g) <= S.MAX_IMAGES_PER_WELL:
        continue
    ranked = g.sort_values(["other_res", "n_beads", "field", "position"], ascending=[True, False, True, True])
    for f in ranked["file"].iloc[S.MAX_IMAGES_PER_WELL:]:
        labels.loc[labels["file"] == f, "status"] = f"extra image, not used (max {S.MAX_IMAGES_PER_WELL} per well)"
over = labels[labels["status"].str.startswith("extra image")]
if len(over):
    say(f"More than {S.MAX_IMAGES_PER_WELL} images in a well; not used (fewest beads): {over['file'].tolist()}")
counts = labels[labels["status"] == "used"].groupby(["well_name", "timepoint"]).size().unstack(fill_value=0)
short = counts[(counts < S.MAX_IMAGES_PER_WELL).any(axis=1)]
if len(short):
    say(f"Wells with fewer than {S.MAX_IMAGES_PER_WELL} images:\n" + short.to_string())
labels.to_csv(out / "file_labels.csv", index=False)
labels = labels[labels["status"] == "used"].copy()
labels["image"] = labels["well_name"] + "." + labels["position"].astype(str) + \
    labels["field"].map(lambda k: "" if k == 0 else "abcdefgh"[k])

beads = beads.merge(labels, on="file")
beads["treatment"] = beads["code"].map(lambda c: S.TREATMENTS[c][0])
beads["dose"] = beads["code"].map(lambda c: S.TREATMENTS[c][1])
ORDER = [S.TREATMENTS[c][0] for c in sorted(S.TREATMENTS, key=lambda c: S.TREATMENTS[c][1])
         if c in set(beads["code"])]
CTRL = S.TREATMENTS[S.CONTROL][0]

# ---- 3. per-bead measures ----------------------------------------------------------------
beads["F"] = beads[f"{S.SIGNAL}_mean"] - beads["bg_mean"]      # counts above local background
beads["SNR"] = beads["F"] / beads["bg_sd"]
if "disc_max" in beads:
    beads["saturated"] = beads["disc_max"] >= S.SATURATION
beads.to_csv(out / "bead_table.csv", index=False)

# ---- 4. images, then wells (the replicate) --------------------------------------------------
agg = dict(file=("file", "first"), n_beads=("F", "size"), F=("F", "mean"), SNR=("SNR", "mean"),
           bg=("bg_mean", "mean"))
if "saturated" in beads:
    agg["pct_saturated"] = ("saturated", "mean")
keys = ["treatment", "dose", "well", "well_name", "timepoint"]
img = beads.groupby(keys + ["image", "position"]).agg(**agg).reset_index()
if "pct_saturated" in img:
    img["pct_saturated"] *= 100
img.to_csv(out / "image_summary.csv", index=False)

cols = [c for c in ["F", "SNR", "bg", "pct_saturated", "n_beads"] if c in img]
per_tp = img.groupby(keys)[cols].mean()
per_tp["n_images"] = img.groupby(keys).size()
wells = per_tp.unstack("timepoint")
wells.columns = [f"{m}_{tp}" for m, tp in wells.columns]
wells = wells.reset_index()
missing = wells[wells["F_before"].isna() | wells["F_after"].isna()]
if len(missing):
    say(f"Wells missing before or after images (left out): {missing['well_name'].tolist()}")
wells = wells.dropna(subset=["F_before", "F_after"]).copy()
wells["dF"] = wells["F_after"] - wells["F_before"]
wells["fold"] = wells["F_after"] / wells["F_before"].where(wells["F_before"] > 0)
before_sd = beads[beads["timepoint"] == "before"].groupby("well")["F"].std()
wells["SNR_change"] = wells["dF"] / wells["well"].map(before_sd)
wells["treatment"] = pd.Categorical(wells["treatment"], ORDER, ordered=True)
wells = wells.sort_values(["treatment", "well"]).reset_index(drop=True)
wells.to_csv(out / "well_summary.csv", index=False)
n_img = img[img["well"].isin(wells["well"])].groupby("timepoint").size()
n_bead = beads[beads["well"].isin(wells["well"])].groupby("timepoint").size()
say(f"Wells compared: {len(wells)}; images before/after: {n_img.get('before', 0)}/{n_img.get('after', 0)}; "
    f"beads before/after: {n_bead.get('before', 0)}/{n_bead.get('after', 0)}")
if log_path.exists() and "out_of_focus" in pd.read_csv(log_path).columns:
    oof = pd.read_csv(log_path).set_index("file")["out_of_focus"]
    used = beads[beads["well"].isin(wells["well"])].groupby(["timepoint", "file"]).size().reset_index(name="kept")
    used["oof"] = used["file"].map(oof).fillna(0)
    t = used.groupby("timepoint")[["kept", "oof"]].sum()
    say("Out-of-focus beads left out by the Fiji macro (transmitted-light focus checks): " + "; ".join(
        f"{tp} {int(r.oof)} of {int(r.kept + r.oof)} ({100 * r.oof / (r.kept + r.oof):.0f}%)" for tp, r in t.iterrows()))

# ---- 5. treatment summary ---------------------------------------------------------------------
M = [c for c in ["F_before", "F_after", "dF", "fold", "SNR_before", "SNR_after", "SNR_change", "bg_before", "bg_after",
                 "pct_saturated_after"] if c in wells]
rows = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    n = len(w)
    row = {"treatment": t, "dose": w["dose"].iat[0] if n else np.nan, "n_wells": n}
    for k in M:
        m, sd = w[k].mean(), w[k].std()
        half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n) if n > 1 else np.nan
        row.update({f"{k}_mean": m, f"{k}_sd": sd, f"{k}_ci95_low": m - half, f"{k}_ci95_high": m + half})
    rows.append(row)
summary = pd.DataFrame(rows)
summary.to_csv(out / "treatment_summary.csv", index=False)
say(f"\nSignal = {S.SIGNAL} mean minus local background (counts).")
show = ["treatment", "n_wells", "F_before_mean", "F_after_mean", "dF_mean", "SNR_before_mean", "SNR_after_mean",
        "bg_after_mean", "pct_saturated_after_mean"]
say(summary[[c for c in show if c in summary]].round(1).to_string(index=False))


# ---- 6. statistics on well values ---------------------------------------------------------------
# The well is the replicate. Outcome = each well's change in bead fluorescence from its own before
# images. Two tests, each answering one question of the study (reasons in README.md):
#   Test 1  Dunnett's test: each probe concentration vs buffer (did the probe do more than buffer?)
#   Test 2  linear regression on log2 concentration, probe wells only (does the effect grow with dose?)
# plus the mean change and 95% CI per treatment, as description.
def fmt_p(p):
    return "n/a" if pd.isna(p) else ("<0.0001" if p < 1e-4 else f"{p:.4f}")


def ci95(v):
    v = np.asarray(v, float)
    if len(v) < 2:
        return np.nan, np.nan
    half = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v))
    return v.mean() - half, v.mean() + half


def tests(change, label, unit, trend_caution):
    say(f"\n=== {label} ===")
    groups = {t: wells.loc[wells["treatment"] == t, change].to_numpy() for t in ORDER}
    say("Change from before to after in each treatment (mean of the wells with 95% CI; a description, not a test)")
    for t, v in groups.items():
        lo, hi = ci95(v)
        say(f"  {t:12s} {v.mean():8.1f} {unit}  (95% CI {lo:.1f} to {hi:.1f}; SD {v.std(ddof=1):.1f}; "
            f"n = {len(v)} wells)")
    treated = [t for t in ORDER if t != CTRL]
    if CTRL not in groups or not treated or any(len(v) < 2 for v in groups.values()):
        say("Not enough wells per treatment (need at least 2 each) for the tests.")
        return
    d = stats.dunnett(*[groups[t] for t in treated], control=groups[CTRL], random_state=0)
    ci = d.confidence_interval()
    say(f"Test 1. Did each probe concentration change the beads more than buffer alone? "
        f"(Dunnett's test, corrected for {len(treated)} comparisons)")
    for i, t in enumerate(treated):
        say(f"  {t:12s} {groups[t].mean() - groups[CTRL].mean():8.1f} {unit} more than buffer "
            f"(95% CI {ci.low[i]:.1f} to {ci.high[i]:.1f}), p = {fmt_p(d.pvalue[i])}")
    probe = wells[(wells["treatment"] != CTRL) & (wells["dose"] > 0)]
    if probe["dose"].nunique() >= 2:
        lr = stats.linregress(np.log2(probe["dose"].astype(float)), probe[change])
        half = stats.t.ppf(0.975, len(probe) - 2) * lr.stderr
        say("Test 2. Does the change grow with concentration? (linear regression on log2 concentration, "
            "probe wells only)")
        say(f"  slope {lr.slope:.1f} {unit} per doubling of concentration (95% CI {lr.slope - half:.1f} to "
            f"{lr.slope + half:.1f}), R² = {lr.rvalue ** 2:.2f}, p = {fmt_p(lr.pvalue)}, n = {len(probe)} wells")
        say(f"  {trend_caution}")


say("\nStatistics: well values (the replicate); outcome = each well's change from its own before images.")
tests("dF", "Bead fluorescence (change in counts above background)", "counts",
      "Caution: beads at the detector maximum have their signal capped (pct_saturated_after), which flattens "
      "this slope. A flat slope does not show that binding is independent of concentration.")

# ---- 7. representative images: typical well, then typical image (by rule, not by eye) ----------
reps = []
for t in ORDER:
    w = wells[wells["treatment"] == t]
    if w.empty:
        continue
    well = w.loc[(w["dF"] - w["dF"].median()).abs().idxmin(), "well"]
    for tp in ("before", "after"):
        cand = img[(img["well"] == well) & (img["timepoint"] == tp)]
        target = w.loc[w["well"] == well, f"F_{tp}"].iat[0]
        r = cand.loc[(cand["F"] - target).abs().idxmin()]
        reps.append({"treatment": t, "timepoint": tp, "well": r["well_name"], "position": r["position"],
                     "file": r["file"], "image_mean_F": round(r["F"], 1), "well_mean_F": round(target, 1)})
pd.DataFrame(reps).to_csv(out / "representative_images.csv", index=False)

# ---- 8. save --------------------------------------------------------------------------------------
say(f"\nSoftware: Python {platform.python_version()}, numpy {np.__version__}, "
    f"pandas {pd.__version__}, scipy {scipy.__version__}")
(out / "stats_report.txt").write_text("\n".join(report), encoding="utf-8")
info = {"order": ORDER, "control": CTRL, "signal": S.SIGNAL, "saturation": S.SATURATION, "units": S.UNITS}
(out / "analysis_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
print(f"\nAnalysis done. Results in {out}")
