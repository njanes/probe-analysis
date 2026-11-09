"""settings.py for exp2: facts about it, used by exp2's analyze.py and make_figures.py.

exp2 is one run with the controls, annexin-V and the probe at 1:3333 and 1:1000, plus before images of a 1:3333
well (W4) from a later run. A well is identified by its number and treatment. Its before/after charts also use
exp1's wells (OTHER_STUDIES), so exp1 is analysed first.
"""

# Treatment word in the file names -> treatment name, in display order. Words are read in lower case without spaces.
GROUPS = {
    "negctrlmfge8": "Negative control (MFG-E8)",            # W1 to W3
    "negctrlgfp": "Negative control (GFP)",                 # W4 to W6
    "annexin": "Annexin-V",                                 # W7 to W9
    "posctrlbsaprecoat": "Positive control (BSA precoat)",  # W12 and W13
    "1to3333": "Probe 1:3333",                              # W14 and W15; the later run's W4 has before images only
    "1to1000": "Probe 1:1000",                              # W10
}

# Treatment names shown differently in the figures
FIGURE_NAMES = {}

# Images in the folder that should not be analysed, and why ({"file name": "reason"})
EXCLUDE = {}

# Files saved under the wrong treatment, read as the name given here ({"file name": "right name"})
RENAME = {}

# Bead signal taken at another detector voltage, scaled to the rest ({"file name": factor})
SCALE = {}

# Each well keeps at most this many images per timepoint: those with the most beads (beads are found in
# transmitted light, so the choice never depends on fluorescence). select_images.py then moves the rest out of the
# folder. None = every image.
MAX_IMAGES_PER_WELL = 3

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Other experiments whose wells the before/after charts use: folder -> words added to its treatment names here
OTHER_STUDIES = {"exp1": "exp1"}

# Before/after bar charts with a dot per well: chart name -> {bar: the treatments whose wells the bar holds}. Fig2
# is exp1's fig2 with this run's annexin-V and 1:3333 wells added (exp1's buffer-only wells are its annexin-V);
# fig5 shows this run, its 1:1000 bar holding exp1's 1:1000 wells and W10, and fig5b is fig5 without BSA.
FIRST_RUN_WITHOUT_BSA = {
    "Negative control (MFG-E8)": ["Negative control (MFG-E8)"],
    "Negative control (GFP)": ["Negative control (GFP)"],
    "Probe 1:1000": ["Probe 1:1000, exp1", "Probe 1:1000"],
}
BEFORE_AFTER = {
    "fig2_before_after": {
        "Annexin-V": ["Buffer only, exp1", "Annexin-V"],
        "Negative control 1:3333": ["Negative control 1:3333, exp1"],
        "Probe 1:3333": ["Probe 1:3333, exp1", "Probe 1:3333"],
    },
    "fig5_before_after_first_run": {**FIRST_RUN_WITHOUT_BSA,
                                    "Positive control (BSA precoat)": ["Positive control (BSA precoat)"]},
    "fig5b_before_after_first_run_without_bsa": FIRST_RUN_WITHOUT_BSA,
}

# Charts whose other bars are each compared with one bar, after treatment (Dunnett's test): chart -> that bar. In
# fig2, the probe is compared with the negative control at 1:3333 instead (Welch's t-test).
COMPARE_TO = {"fig5_before_after_first_run": "Probe 1:1000",
              "fig5b_before_after_first_run_without_bsa": "Probe 1:1000"}

# The other figures: figure name -> its treatments, or None for every treatment. Each has a version without BSA.
WITHOUT_BSA = [t for t in GROUPS.values() if t != "Positive control (BSA precoat)"]
REPRESENTATIVE_IMAGES = {"fig0_representative_images": None,
                         "fig0b_representative_images_without_bsa": WITHOUT_BSA}
POSITIVE_BEADS = {"fig3_positive_beads": None, "fig3b_positive_beads_without_bsa": WITHOUT_BSA}
CHANGE_PER_WELL = {"fig4_change_per_well": None, "fig4b_change_per_well_without_bsa": WITHOUT_BSA}
