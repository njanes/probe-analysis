"""settings.py for exp3: facts about it, used by exp3's analyze.py and make_figures.py.

exp3 is one run in which every well had media (the M in the file names): the MFG-E8 and GFP negative controls
and the BSA-precoat positive control. Its after images of W1_3 and W9 were also taken with the
fluorescence detector at 400 V instead of 360 V (marked 400HV); W7's only after image was taken that way.
"""

# Treatment word in the file names -> treatment name, in display order. Words are read in lower case without spaces.
GROUPS = {
    "mnegvectrl_1to1000": "Negative control (MFG-E8)",     # W1 to W3
    "mgfponly_1to1000": "Negative control (GFP)",          # W4 to W6
    "mposctrl_1to1000": "Positive control (BSA precoat)",  # W7 to W9
}

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

MAX_IMAGES_PER_WELL = None         # no limit: every image of a well is used

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Fig2, the before/after bar chart with a dot per well: its treatments, in order. Each is tested before vs after
# only, as exp3 has no probe-only wells to compare the others with.
BEFORE_AFTER = ["Negative control (MFG-E8)", "Negative control (GFP)", "Positive control (BSA precoat)"]

# Treatments in the other figures: treatment names, or None for every treatment
REPRESENTATIVE_IMAGES = None       # fig0
POSITIVE_BEADS = None              # fig3
CHANGE_PER_WELL = None             # fig4
