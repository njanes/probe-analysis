"""settings.py for study3: the third run, used by analyze.py when run as  python analyze.py study3. Same form as the
project folder's settings.py. Its images go into study3/images with the names they were saved under (bead images
only: names starting with before_ or after_). It makes no figures of its own: study2's fig6 uses its 1:1000 wells,
so it is analysed before study2.

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

# Images that should not be analysed, and why ({"file name": "reason"})
EXCLUDE = {}

MAX_IMAGES_PER_WELL = None         # no limit: every image of a well is used

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# No figures for this study
BEFORE_AFTER = {}
WELL_DOTS = True
COMPARE_TO = {}
REPRESENTATIVE_IMAGES = []         # fig0
POSITIVE_BEADS = []                # fig3
CHANGE_PER_WELL = []               # fig4

# Other studies whose wells the before/after charts can use
OTHER_STUDIES = {}
