"""settings.py: facts about this study, used by analyze.py and make_figures.py.

Images are labelled from their file names (the naming convention is in README.md), so new images
that follow it are analysed without changing anything here. A study in its own folder (such as
study2) has a settings.py of its own, in the same form.
"""

# Treatment word in the file names -> treatment name, in display order (controls first). A word with a dilution
# ("probe-1to400") is read as the word before "-1to" with the dilution added ("Probe 1:400"), and each is shown
# from most to least diluted. Words are read in lower case without spaces; a word set to None is not analysed.
# The tests look for the names "Buffer only", "Negative control 1:N" and "Probe 1:N" (README.md).
GROUPS = {"buffer": "Buffer only", "negctrl": "Negative control", "probe": "Probe"}

# Treatment names shown differently in the figures
FIGURE_NAMES = {"Buffer only": "Annexin-V"}

# Images in the images folder that should not be analysed, and why ({"file name": "reason"}).
# Background images (position "background") are left out without being listed here.
EXCLUDE = {}

# Each well keeps at most this many images per timepoint: those with the most beads (beads are found
# in transmitted light, so the choice never depends on fluorescence). None = every image.
MAX_IMAGES_PER_WELL = 3

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated

# Before/after bar charts: chart name -> {bar: the treatments whose wells the bar holds}
BEFORE_AFTER = {"fig2_before_after": {"Buffer only": ["Buffer only"],
                                      "Negative control 1:3333": ["Negative control 1:3333"],
                                      "Probe 1:3333": ["Probe 1:3333"]}}
WELL_DOTS = False                  # a dot for each well on the before/after bars
# Charts whose other bars are each compared with one bar, after treatment (Dunnett's test): chart -> that bar
COMPARE_TO = {}

# Treatments in the other figures: treatment names (a name without its dilution, such as "Probe", takes in all of
# its dilutions), None for every treatment, or [] for no figure
REPRESENTATIVE_IMAGES = None                                                   # fig0
POSITIVE_BEADS = ["Probe 1:10000", "Probe 1:3333", "Probe 1:200"]              # fig3
CHANGE_PER_WELL = ["Probe"]                                                    # fig4

# Other studies whose wells the before/after charts can use: folder -> words added to its treatment names here
OTHER_STUDIES = {}
