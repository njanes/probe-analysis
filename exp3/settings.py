"""settings.py for exp3: facts about it, used by exp3's analyze.py and make_figures.py.

exp3 holds two runs. In the media run every well had media (the M in the file names): the MFG-E8 and GFP negative
controls and the BSA-precoat positive control. Its after images of W1_3 and W9 were also taken with the
fluorescence detector at 400 V instead of 360 V (marked 400HV); W7's only after image was taken that way. The later
probe run has the probe at 1:1000 (W1 to W3, without media). A well is identified by its number and treatment, so
the probe run's W1 to W3 are different wells from the media run's.
"""

# Treatment word in the file names -> treatment name, in display order. Words are read in lower case without spaces.
GROUPS = {
    "mnegvectrl_1to1000": "Negative control (MFG-E8)",     # media run, W1 to W3
    "mgfponly_1to1000": "Negative control (GFP)",          # media run, W4 to W6
    "mposctrl_1to1000": "Positive control (BSA precoat)",  # media run, W7 to W9
    "1to1000": "Probe 1:1000",                             # probe run, W1 to W3
}

# Treatment names shown differently in the figures
FIGURE_NAMES = {}

# Images in the folder that should not be analysed, and why ({"file name": "reason"})
EXCLUDE = {name: "400HV retake of a field also imaged at 360 V, which is used" for name in [
    "after_ Mnegvectrl_1to1000_W1_3(400HV).oir",
    "after_ Mposctrl_1to1000_W9_1(400HV).oir",
    "after_ Mposctrl_1to1000_W9_2(400HV).oir",
    "after_ Mposctrl_1to1000_W9_3 (400HV).oir",
]}

# Files saved under the wrong treatment, read as the name given here: W7 is a positive-control well (its before
# images are Mposctrl)
RENAME = {"after_ Mgfponly_1to1000_W7_3 (400HV).oir": "after_ Mposctrl_1to1000_W7_3 (400HV).oir"}

# Bead signal taken at 400 V, scaled to 360 V like the rest: file -> factor. At 400 V the same beads read 2.2 times
# as bright (the 9 beads found in the W9 fields imaged at both voltages: slope of their signal at 400 V against
# 360 V), so the factor is 1 / 2.2.
SCALE = {"after_ Mgfponly_1to1000_W7_3 (400HV).oir": 0.45}

# Each well keeps at most this many images per timepoint: those with the most beads (beads are found in
# transmitted light, so the choice never depends on fluorescence). select_images.py then moves the rest out of the
# folder. None = every image.
MAX_IMAGES_PER_WELL = 3

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Other experiments whose wells the before/after charts use: folder -> words added to its treatment names here
OTHER_STUDIES = {}

# Before/after bar charts with a dot per well: chart name -> {bar: the treatments whose wells the bar holds}. Fig6
# shows the media run beside the probe run's 1:1000 and fig6b the media run alone; fig6c and fig6d are fig6 and
# fig6b without BSA. Fig7 shows the probe run alone.
NEGATIVE_CONTROLS = {
    "Negative control (MFG-E8)": ["Negative control (MFG-E8)"],
    "Negative control (GFP)": ["Negative control (GFP)"],
}
MEDIA_RUN = {**NEGATIVE_CONTROLS, "Positive control (BSA precoat)": ["Positive control (BSA precoat)"]}
BEFORE_AFTER = {
    "fig6_before_after_second_run": {**MEDIA_RUN, "Probe 1:1000": ["Probe 1:1000"]},
    "fig6b_before_after_second_run_without_probe": MEDIA_RUN,
    "fig6c_before_after_second_run_without_bsa": {**NEGATIVE_CONTROLS, "Probe 1:1000": ["Probe 1:1000"]},
    "fig6d_before_after_second_run_without_probe_or_bsa": NEGATIVE_CONTROLS,
    "fig7_before_after_third_run": {"Probe 1:1000": ["Probe 1:1000"]},
}

# Charts whose other bars are each compared with one bar, after treatment (Dunnett's test): chart -> that bar
COMPARE_TO = {"fig6_before_after_second_run": "Probe 1:1000",
              "fig6c_before_after_second_run_without_bsa": "Probe 1:1000"}

# The other figures: figure name -> its treatments, or None for every treatment. Each has a version without BSA.
WITHOUT_BSA = [t for t in GROUPS.values() if t != "Positive control (BSA precoat)"]
REPRESENTATIVE_IMAGES = {"fig0_representative_images": None,
                         "fig0b_representative_images_without_bsa": WITHOUT_BSA}
POSITIVE_BEADS = {"fig3_positive_beads": None, "fig3b_positive_beads_without_bsa": WITHOUT_BSA}
CHANGE_PER_WELL = {"fig4_change_per_well": None, "fig4b_change_per_well_without_bsa": WITHOUT_BSA}
