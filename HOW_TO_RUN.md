# How to run the bead analysis

There are three steps, run in this order. Each one uses what the step before it made.

| Step | File | What it does |
|---|---|---|
| 1 | `bead_segmentation.ijm` | A Fiji macro. Finds the beads in every image and measures how bright each one is. |
| 2 | `analyze.py` | Turns those measurements into a result for each well and treatment, and runs the statistics. |
| 3 | `make_figures.py` | Makes the figures from those results. |

`settings.py` holds a few fixed settings the two Python scripts share. You don't need to run or change it.

## Before the first run

1. Install [Fiji](https://fiji.sc).
2. Install [Python](https://www.python.org/downloads/) (3.10 or newer). On Windows, tick "Add python.exe
   to PATH" in the installer.
3. Open a terminal in this folder and install the packages the scripts need (only needed once):

   ```
   python -m pip install -r requirements.txt
   ```

   To open a terminal in this folder on Windows: open the folder in File Explorer, type `cmd` in the
   address bar and press Enter.

On a Mac, type `python3` instead of `python` here and below.

## Running it

1. **Fiji macro**
   - Make a new, empty folder called `results` in this folder. If there is already a `results`
     folder, rename it or move it somewhere else first.
   - In Fiji: File > Open..., choose `bead_segmentation.ijm`, then press Run.
   - It asks for two folders: choose `images` first, then `results`.
   - A settings window opens. Click OK without changing anything.
   - Wait for it to finish; it goes through every image, so it takes a while.
2. **Analysis:** in the terminal, in this folder, run `python analyze.py`
3. **Figures:** then run `python make_figures.py`

## Where to find the results

Everything is in `results/analysis`:

- `figures.html`: all four figures on one page; open it in a web browser. It works on its own, so it
  can be sent to someone as a single file.
- `stats_report.txt`: all the numbers and test results in one place.
- `fig0_representative_images.png`, `fig1_dilution_response.png`, `fig2_before_after.png` and
  `fig3_positive_beads.png`: the figures (each also saved as .svg for editing).
- The .csv tables, which open in Excel.

To check that the beads were found correctly, look at the images in `results/qc`: beads that were
measured are outlined in cyan, out-of-focus beads (left out) in magenta, and other rejected objects
in orange.

## Adding new images

1. Name each image the same way as the others: before or after, the treatment, the well and the
   position. For example, `after_probe-1to1000_W02_3.oir` means after treatment, probe at 1:1000,
   well 2, position 3.
   - Treatments are written `buffer`, `negctrl-1to3333` (negative control at 1:3333) or
     `probe-1to1000` (probe at 1:1000).
   - If you repeat a treatment, give it well numbers that treatment hasn't used before.
   - For a background image, write `background` in place of the position; it is skipped.
2. Put the new images in the `images` folder.
3. Run all three steps again, with a new, empty `results` folder.

The new images are added to the results and figures automatically. `README.md` has the full details
of the analysis.
