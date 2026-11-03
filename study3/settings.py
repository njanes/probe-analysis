"""settings.py for study3: the third run, used by analyze.py and make_figures.py when run as
python analyze.py study3  and  python make_figures.py study3. Same form as the project folder's settings.py.
Its images go into study3/images with the names they were saved under. It makes its own figures, and study2's fig6
uses its 1:1000 wells, so it is analysed before study2.

It has its own folder because it uses the same words as study2's first run ("1to1000", "1to3333"), so in one
folder their wells would mix.
"""

# Treatment word in the file names -> treatment name. Words are read in lower case without spaces.
GROUPS = {
    "1to1000": "Probe 1:1000",     # W1 to W3
    "1to3333": None,               # W4: before images only, so left out
}

# Treatment names shown differently in the figures
FIGURE_NAMES = {}

# Images that should not be analysed, and why ({"file name": "reason"}): cell images saved in the same folder
EXCLUDE = {name + ".oir": "cell image, not beads" for name in [
    "Arantxa_60x_10.29_diffSY5Y_P", "Arantxa_60x_10.29_diffSY5Y_P_0001", "Arantxa_60x_10.29_diffSY5Y_P_0002",
    "Arantxa_60x_10.29_diffSY5Y_StpP", "Arantxa_60x_10.29_diffSY5Y_StpP_0001", "Arantxa_60x_10.29_diffSY5Y_StpP_0002",
    "Arantxa_60x_10.29_diffSY5Y_StpPDD", "Arantxa_60x_10.29_diffSY5Y_StpPDD_0001",
    "Arantxa_60x_10.29_diffSY5Y_StpPDD_0002", "Arantxa_60x_10.29_diffSY5Y_StpPTD",
    "Arantxa_60x_10.29_diffSY5Y_StpPTD_0001", "Arantxa_60x_10.29_diffSY5Y_StpPTD_0002",
    "Arantxa_60x_10.29_diffSY5Y_StpPTD_0003",
]}

MAX_IMAGES_PER_WELL = None         # no limit: every image of a well is used

# A well with usable after images but no usable before images: True = it gets the mean before values of
# its treatment's other wells and is compared like them (the report lists it), False = it is left out
BORROW_BEFORE = True  # W1: no usable before images

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Before/after bar chart, in the style of the other studies' (the dilution-response curve, fig1, needs 4 dilutions)
BEFORE_AFTER = {"fig7_before_after_third_run": {"Probe 1:1000": ["Probe 1:1000"]}}
WELL_DOTS = True                   # a dot for each well on the before/after bars
COMPARE_TO = {}

# Treatments in the other figures (None = every treatment)
REPRESENTATIVE_IMAGES = None       # fig0
POSITIVE_BEADS = None              # fig3
CHANGE_PER_WELL = None             # fig4

# Other studies whose wells the before/after charts can use. The first study ("." is the project folder) is listed
# for its probe dilutions only, so 1:1000 is drawn in the same blue as in the other studies' figures.
OTHER_STUDIES = {".": "first study"}
