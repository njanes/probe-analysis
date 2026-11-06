"""
select_images.py: moves the images an experiment's analysis didn't use out of its folder, into not_selected/ inside
it, so the folder holds only the images analysed: at most 3 before and 3 after per well (MAX_IMAGES_PER_WELL).

Run from the project folder after the Fiji macro and the experiment's analyze.py, naming the experiment's folder:
  python select_images.py exp2

It moves every image analyze.py listed in results/analysis/images_not_used.csv: those beyond a well's best 3 (the
fewest beads in transmitted light), the first save of a field saved twice, images in EXCLUDE, background images
and images with no beads. An image whose name couldn't be read stays, so analyze.py keeps warning about it.
Nothing is deleted: not_selected/selection.csv lists every image moved and why, and moving an image back into the
experiment's folder undoes it. The Fiji macro doesn't look in subfolders, so its next run sees only the images left.
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

if len(sys.argv) != 2:
    sys.exit("Name the experiment's folder, such as: python select_images.py exp2")
FOLDER = Path(sys.argv[1])
LIST = FOLDER / "results" / "analysis" / "images_not_used.csv"
if not LIST.exists():
    sys.exit(f"{LIST} not found: run the Fiji macro and then {FOLDER / 'analyze.py'} first")

not_used = pd.read_csv(LIST)
move = not_used[[(FOLDER / f).is_file() for f in not_used["file"]]]   # still in the folder (not moved before)
if move.empty:
    sys.exit(f"Nothing to move: every image left in {FOLDER} is used.")
OUT = FOLDER / "not_selected"
OUT.mkdir(exist_ok=True)
for f in move["file"]:
    shutil.move(FOLDER / f, OUT / f)
record = OUT / "selection.csv"
move.to_csv(record, mode="a", header=not record.exists(), index=False)

print(f"Moved {len(move)} image(s) to {OUT} (each listed with its reason in {record}):")
for why, n in move["reason"].value_counts().items():
    print(f"  {n:3d}  {why}")
print("\nThe results are the same as before. To make the results folder list only the images left, run the Fiji "
      "macro again into a new, empty results folder, then analyze.py and make_figures.py.")
