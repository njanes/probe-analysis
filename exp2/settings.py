"""settings.py for exp2: facts about it, used by exp2's analyze.py and make_figures.py.

exp2 holds two runs: an earlier one with the controls, annexin-V and the probe at 1:3333 and 1:1000, and a later
one with more 1:1000 wells (W1 to W3) and before images of a 1:3333 well (W4). A well is identified by its number
and treatment, so the later run's W1 to W3 (1:1000) are different wells from the earlier run's W1 to W3 (MFG-E8).
"""

# Treatment word in the file names -> treatment name, in display order. Words are read in lower case without spaces.
GROUPS = {
    "negctrlmfge8": "Negative control (MFG-E8)",            # W1 to W3
    "negctrlgfp": "Negative control (GFP)",                 # W4 to W6
    "annexin": "Annexin-V",                                 # W7 to W9
    "posctrlbsaprecoat": "Positive control (BSA precoat)",  # W12 and W13
    "1to3333": "Probe 1:3333",                              # W14 and W15; the later run's W4 has before images only
    "1to1000": "Probe 1:1000",                              # W10; the later run's W1 to W3
}

# Images in the folder that should not be analysed, and why ({"file name": "reason"})
EXCLUDE = {}

# Each well keeps at most this many images per timepoint: those with the most beads (beads are found in
# transmitted light, so the choice never depends on fluorescence). select_images.py then moves the rest out of the
# folder. None = every image.
MAX_IMAGES_PER_WELL = 3

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Fig2, the before/after bar chart with a dot per well: its treatments, in order (1:1000 last, so it can be
# cropped off)
BEFORE_AFTER = ["Negative control (MFG-E8)", "Negative control (GFP)", "Annexin-V", "Positive control (BSA precoat)",
                "Probe 1:3333", "Probe 1:1000"]
COMPARE_TO = "Probe 1:1000"        # fig2: every other treatment's after fluorescence vs this one's (Dunnett's test)

# Treatments in the other figures: treatment names, or None for every treatment
REPRESENTATIVE_IMAGES = None       # fig0
POSITIVE_BEADS = None              # fig3
CHANGE_PER_WELL = None             # fig4
