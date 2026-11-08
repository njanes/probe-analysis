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
# fig5 shows this run, its 1:1000 bar holding exp1's 1:1000 wells and W10.
BEFORE_AFTER = {
    "fig2_before_after": {
        "Annexin-V": ["Buffer only, exp1", "Annexin-V"],
        "Negative control 1:3333": ["Negative control 1:3333, exp1"],
        "Probe 1:3333": ["Probe 1:3333, exp1", "Probe 1:3333"],
    },
    "fig5_before_after_first_run": {
        "Negative control (MFG-E8)": ["Negative control (MFG-E8)"],
        "Negative control (GFP)": ["Negative control (GFP)"],
        "Probe 1:1000": ["Probe 1:1000, exp1", "Probe 1:1000"],
        "Positive control (BSA precoat)": ["Positive control (BSA precoat)"],
    },
}

# Charts whose other bars are each compared with one bar, after treatment (Dunnett's test): chart -> that bar. In
# fig2, the probe is compared with the negative control at 1:3333 instead (Welch's t-test).
COMPARE_TO = {"fig5_before_after_first_run": "Probe 1:1000"}

# Treatments in the other figures: treatment names, or None for every treatment
REPRESENTATIVE_IMAGES = None       # fig0
POSITIVE_BEADS = None              # fig3
CHANGE_PER_WELL = None             # fig4
