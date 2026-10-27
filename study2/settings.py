"""settings.py for study2: two runs analysed together, used by analyze.py and make_figures.py when run as
python analyze.py study2  and  python make_figures.py study2. Same form as the project folder's settings.py.

The images of both runs go into study2/images with the names they were saved under. A well imaged in both
runs is one well: the second run's images are further images of the same well.
"""

# Treatment word in the file names -> treatment name, in display order. Words are read in lower case without
# spaces. The two runs used different words for three of the treatments, so those words share a name.
GROUPS = {
    "annexin": "Annexin-V",                                  # W7 to W9
    "mposctrl_1to1000": "Annexin-V",                         # second run, W7 to W9
    "negctrlmfge8": "Negative control (MFG-E8)",             # W1 to W3
    "mnegvectrl_1to1000": "Negative control (MFG-E8)",       # second run, W1 to W3
    "negctrlgfp": "Negative control (GFP)",                  # W4 to W6
    "mgfponly_1to1000": "Negative control (GFP)",            # second run, W4 to W6
    "posctrlbsaprecoat": "Positive control (BSA precoat)",   # W12 and W13
    "1to3333": "Probe 1:3333",                               # W14 and W15
    "1to1000": "Probe 1:1000",                               # W10
    "dontuse": None,                                         # W16 and W17, marked not to use: left out
}

# Treatment names shown differently in the figures
FIGURE_NAMES = {}

# Images that should not be analysed, and why ({"file name": "reason"})
EXCLUDE = {}

MAX_IMAGES_PER_WELL = None         # no limit: every image of a well is used

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Treatments in each figure (None = every treatment)
BEFORE_AFTER = None                # fig2
POSITIVE_BEADS = None              # fig3
CHANGE_PER_WELL = None             # fig4
