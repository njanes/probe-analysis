"""
settings.py: facts about this experiment, used by analyze.py and make_figures.py.
"""

# Treatment of each well, from the plate map. The codes in the file names can't be used:
# they don't match the concentrations (P0.5 = Probe 0.25, P1 = Probe 0.5, P2 = Probe 1),
# and W4 and W7 carry the previous group's code.
PLATE_MAP = {
    1: "Probe 0.25", 2: "Probe 0.25", 3: "Probe 0.25",
    4: "Probe 0.5", 5: "Probe 0.5", 6: "Probe 0.5",
    7: "Probe 1", 8: "Probe 1", 9: "Probe 1",
    10: "Buffer only", 11: "Buffer only", 12: "Buffer only",
}
DOSE = {"Buffer only": 0.0, "Probe 0.25": 0.25, "Probe 0.5": 0.5, "Probe 1": 1.0}   # per 100 µL
ORDER = list(DOSE)                 # order of treatments in tables and figures
CONTROL = "Buffer only"

# Images not used, and why.
# Positions saved more than once (_0001, _0002) were compared by their bead positions:
# saves of the same field are retakes (the latest is used); saves of a different field are
# extra images. Wells keep at most 3 images per timepoint: full resolution first, then the
# most beads (beads are found in transmitted light, so this never depends on fluorescence).
EXCLUDE = {
    "AD_2026.09.23-BW1.1.oir": "retake of the same field as BW1.1_0002",
    "AD_2026.09.23-BW1.1_0001.oir": "retake of the same field as BW1.1_0002",
    "AD_2026.09.23-BW5.1.oir": "retake of the same field as BW5.1_0001",
    "AD_2026.09.23-BW5.2.oir": "retake of the same field as BW5.2_0001",
    "AD_2026.09.23-BW5.3.oir": "retake of the same field as BW5.3_0001",
    "AD_2026.09.23-BW10.1.oir": "retake of the same field as BW10.1_0001",
    "AD_2026.09.23-BW11.2.oir": "retake of the same field as BW11.2_0001",
    "AD_2026.09.24_AP0.5W1.1.oir": "retake of the same field as AP0.5W1.1_0001",
    "AD_2026.09.23-BW7.1.oir": "4th image in the well, fewest beads",
    "AD_2026.09.24_AP1W5.3.oir": "4th image in the well, fewest beads",
    "AD_2026.09.24_AP2W8.3.oir": "4th image in the well, fewest beads",
    "AD_2026.09.24_AP2W9.2.oir": "4th image in the well, fewest beads",
    # Well 4's first after-treatment pass (24 Sept, 12:59 to 13:02) shows untreated beads and
    # untreated background (29 counts, like the before images), unlike its second pass 5 minutes
    # later; it looks like it was imaged before the probe was added.
    "AD_2026.09.24_AP0.5W4.1.oir": "W4 first pass: looks untreated",
    "AD_2026.09.24_AP0.5W4.2.oir": "W4 first pass: looks untreated",
    "AD_2026.09.24_AP0.5W4.2_0001.oir": "W4 first pass: looks untreated",
    "AD_2026.09.24_AP0.5W4.3.oir": "W4 first pass: looks untreated",
}

SATURATION = 4095                  # detector maximum (12-bit); beads with any pixel at it are saturated

# Figure colours: grey for buffer, three blues for the probe concentrations
COLORS = {"Buffer only": "#898781", "Probe 0.25": "#6da7ec", "Probe 0.5": "#2a78d6", "Probe 1": "#184f95"}
