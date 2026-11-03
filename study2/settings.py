"""settings.py for study2: two runs, used by analyze.py and make_figures.py when run as
python analyze.py study2  and  python make_figures.py study2. Same form as the project folder's settings.py.

The images of both runs go into study2/images with the names they were saved under. Each run's wells are its own:
the second run's treatment names end in ", second run", so its W1 is a different well from the first run's W1.
"""

# Treatment word in the file names -> treatment name, in display order. Words are read in lower case without spaces.
GROUPS = {
    "negctrlmfge8": "Negative control (MFG-E8)",                     # first run, W1 to W3
    "negctrlgfp": "Negative control (GFP)",                          # first run, W4 to W6
    "annexin": "Annexin-V",                                          # first run, W7 to W9
    "1to1000": "Probe 1:1000",                                       # first run, W10
    "posctrlbsaprecoat": "Positive control (BSA precoat)",           # first run, W12 and W13
    "1to3333": "Probe 1:3333",                                       # first run, W14 and W15
    "dontuse": None,                                                 # first run, W16 and W17, marked not to use
    "mnegvectrl_1to1000": "Negative control (MFG-E8), second run",   # second run, W1 to W3
    "mgfponly_1to1000": "Negative control (GFP), second run",        # second run, W4 to W6
    "mposctrl_1to1000": "Annexin-V, second run",                     # second run, W7 to W9
}

# Treatment names shown differently in the figures
FIGURE_NAMES = {}

# Images that should not be analysed, and why ({"file name": "reason"}): those taken at 400HV
EXCLUDE = {name: "taken at 400HV; not used" for name in [
    "after_ Mnegvectrl_1to1000_W1_3(400HV).oir",
    "after_ Mgfponly_1to1000_W7_3 (400HV).oir",
    "after_ Mposctrl_1to1000_W9_1(400HV).oir",
    "after_ Mposctrl_1to1000_W9_2(400HV).oir",
    "after_ Mposctrl_1to1000_W9_3 (400HV).oir",
]}

MAX_IMAGES_PER_WELL = None         # no limit: every image of a well is used

# A well with usable after images but no usable before images: True = it gets the mean before values of
# its treatment's other wells and is compared like them (the report lists it), False = it is left out
BORROW_BEFORE = False

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Before/after bar charts: chart name -> {bar: the treatments whose wells the bar holds}. Fig2 is the first study's
# fig2 with this study's annexin-V and 1:3333 wells added; fig5 and fig6 show the first and second runs, and fig6b
# is fig6 without the 1:1000s, fig6c with the recent one only. In fig5, 1:1000 holds the first study's 1:1000 wells
# and the first run's W10; fig6 shows those as the previous 1:1000, beside the recent one: the third run's W1 to W3
# (study3).
BEFORE_AFTER = {
    "fig2_before_after": {
        "Annexin-V": ["Buffer only, first study", "Annexin-V", "Annexin-V, second run"],
        "Negative control 1:3333": ["Negative control 1:3333, first study"],
        "Probe 1:3333": ["Probe 1:3333, first study", "Probe 1:3333"],
    },
    "fig5_before_after_first_run": {
        "Negative control (MFG-E8)": ["Negative control (MFG-E8)"],
        "Negative control (GFP)": ["Negative control (GFP)"],
        "Probe 1:1000": ["Probe 1:1000, first study", "Probe 1:1000"],
        "Positive control (BSA precoat)": ["Positive control (BSA precoat)"],
    },
    "fig6_before_after_second_run": {   # the second run had no probe, so the two 1:1000s are last, to crop
        "Negative control (MFG-E8)": ["Negative control (MFG-E8), second run"],
        "Negative control (GFP)": ["Negative control (GFP), second run"],
        "Probe 1:1000 (previous)": ["Probe 1:1000, first study", "Probe 1:1000"],
        "Probe 1:1000 (recent)": ["Probe 1:1000, third run"],
    },
    "fig6b_before_after_second_run_without_probe": {   # fig6 without the 1:1000, on its own scale
        "Negative control (MFG-E8)": ["Negative control (MFG-E8), second run"],
        "Negative control (GFP)": ["Negative control (GFP), second run"],
    },
    "fig6c_before_after_second_run_recent_probe": {     # fig6 with the recent 1:1000 only
        "Negative control (MFG-E8)": ["Negative control (MFG-E8), second run"],
        "Negative control (GFP)": ["Negative control (GFP), second run"],
        "Probe 1:1000 (recent)": ["Probe 1:1000, third run"],
    },
}

WELL_DOTS = True                   # a dot for each well on the before/after bars

# Charts whose other bars are each compared with one bar, after treatment (Dunnett's test): chart -> that bar, or a
# list of bars (each pair compared once). In fig6, every bar vs the previous 1:1000, then the negative controls vs
# the recent 1:1000.
COMPARE_TO = {"fig5_before_after_first_run": "Probe 1:1000",
              "fig6_before_after_second_run": ["Probe 1:1000 (previous)", "Probe 1:1000 (recent)"],
              "fig6c_before_after_second_run_recent_probe": "Probe 1:1000 (recent)"}

# No other figures for this study
REPRESENTATIVE_IMAGES = []         # fig0
POSITIVE_BEADS = []                # fig3
CHANGE_PER_WELL = []               # fig4

# Other studies whose wells the before/after charts can use: folder -> words added to its treatment names here.
# Each is analysed before this one (its results/analysis/well_summary.csv): "." is the project folder, the first
# study; study3 is the third run.
OTHER_STUDIES = {".": "first study", "study3": "third run"}
