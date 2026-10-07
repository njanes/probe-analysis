"""settings.py: facts about this study, used by analyze.py and make_figures.py.

Images are labelled from their file names (the naming convention is in README.md), so new images
that follow it are analysed without changing anything here.
"""

# Treatment word in the file names -> label, in display order (controls first). A dilution in the name
# is added to the label ("probe-1to400" -> "Probe 1:400"), and each kind is shown from most to least diluted.
KINDS = {"buffer": "Buffer only", "negctrl": "Negative control", "probe": "Probe"}

# Images in the images folder that should not be analysed, and why ({"file name": "reason"}).
# Background images (position "background") are left out without being listed here.
EXCLUDE = {}

# Each well keeps at most this many images per timepoint: those with the most beads (beads are found
# in transmitted light, so the choice never depends on fluorescence)
MAX_IMAGES_PER_WELL = 3

SATURATION = 4095                  # detector maximum (12-bit); a bead with any pixel at it is saturated
