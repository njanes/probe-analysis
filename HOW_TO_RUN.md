# How to run the bead analysis

The analysis is split into three experiments, each in its own folder:

| Folder | Experiment | Images in it (by the treatment word in the file name) |
|---|---|---|
| `exp1` | the first study | `buffer`, `negctrl-1to3333`, `probe-1to…` |
| `exp2` | MFG-E8, GFP, annexin-V, BSA precoat and the probe at 1:3333 and 1:1000 | `negctrlMFGE8`, `negctrlGFP`, `annexin`, `posctrlBSAprecoat`, `1to3333`, `1to1000` |
| `exp3` | the media run (M = media in every well): MFG-E8, GFP and BSA precoat | `Mnegvectrl_1to1000`, `Mgfponly_1to1000`, `Mposctrl_1to1000` |

Each folder holds that experiment's images (the .oir files, straight in the folder) and everything made
for it alone:

| File | What it is |
|---|---|
| `segmentation_settings.txt` | the bead-finding settings tuned for this experiment's images, loaded by the Fiji macro |
| `settings.py` | treatment names, images to leave out and which figures to make; you don't need to run or change it |
| `analyze.py` | turns the Fiji measurements into a result for each well and treatment, and runs the statistics |
| `make_figures.py` | makes this experiment's figures from those results |
| `results/` | everything the three steps make (you create it empty before the first step) |

The two Fiji macros, `bead_segmentation.ijm` and `edit_beads.ijm`, are in the project folder and work
for every experiment.

To get the latest version of the scripts, run `git pull` in the terminal in the project folder. It
doesn't touch the images or `results` folders.

## Before the first run

1. Install [Fiji](https://fiji.sc).
2. Install [Python](https://www.python.org/downloads/) (3.10 or newer). On Windows, tick "Add python.exe
   to PATH" in the installer.
3. Open a terminal in the project folder and install the packages the scripts need (only needed once):

   ```
   python -m pip install -r requirements.txt
   ```

   To open a terminal in the project folder on Windows: open the folder in File Explorer, type `cmd`
   in the address bar and press Enter.
4. Put each image in its experiment's folder, using the table above. Keep the names the images were
   saved under; don't rename anything. exp1's images are the ones in the project's `images` folder:
   copy them into `exp1`.

On a Mac, type `python3` instead of `python` here and below.

## Running it

The three steps, for one experiment at a time (exp2 here; for another, change `exp2` to its folder):

1. **Fiji macro**
   - Make a new, empty folder called `results` inside `exp2`. If there is already a `results` folder,
     rename it or move it somewhere else first. (Choosing a folder that already has results only
     updates it with your corrected outlines: see "Correcting the bead outlines by hand" below.)
   - In Fiji: File > Open..., choose `bead_segmentation.ijm` (in the project folder), then press Run.
   - It asks for two folders: choose `exp2` first, then `exp2/results`.
   - The settings window opens with exp2's tuned settings, and says so at the top. Click OK without
     changing anything.
   - Wait for it to finish; it goes through every image, so it takes a while.
2. **Analysis:** in the terminal, in the project folder, run `python exp2/analyze.py`
3. **Figures:** then run `python exp2/make_figures.py`

If something had to be left out (an image whose name can't be read, a treatment with no usable beads),
the terminal says how many warnings there were, and each one is a WARNING line in `stats_report.txt`.

## Keeping only the best 3 images per well

The analysis uses at most 3 images per well before treatment and 3 after: those with the most beads,
counted in transmitted light, so the choice never depends on how bright the beads are. To keep only
those images in the experiment's folder:

1. Run the three steps above as usual.
2. In the terminal, in the project folder, run `python select_images.py exp2`.

It moves every image the analysis didn't use into a `not_selected` folder inside `exp2`, and lists each
one with the reason in `not_selected/selection.csv`. That covers images beyond a well's best 3, the first
save of a field saved twice, images left out in `settings.py`, background images and images with no
beads. The results don't change. If you'd like the `results` folder to mention only the images left, run
the three steps again with a new, empty `results` folder.

Nothing is deleted: to put an image back, move it from `not_selected` into the experiment's folder.

## Where to find the results

Everything is in the experiment's `results/analysis` folder:

- `figures.html`: all the figures on one page; open it in a web browser. It works on its own, so it
  can be sent to someone as a single file.
- `stats_report.txt`: all the numbers and test results in one place, including every image that
  wasn't used and why.
- The figures (each also saved as .svg for editing). Each figure number means the same kind of figure
  in every experiment:
  - `fig0_representative_images`: a typical before and after image for each treatment.
  - `fig1_dilution_response` (exp1 only): the dilution-response curve.
  - `fig2_before_after`: mean fluorescence before and after for each treatment. In exp2 and exp3 it
    has a dot for each well. In exp2, every other treatment is compared with the probe at 1:1000; in
    exp3, which has no probe-only wells, each treatment is tested before vs after only.
  - `fig3_positive_beads`: the % of beads positive after treatment.
  - `fig4_change_per_well`: each well's change in fluorescence.
- The .csv tables, which open in Excel.

To check that the beads were found correctly, look at the images in `results/qc`: beads that were
measured are outlined in cyan, out-of-focus beads (left out) in magenta, and other rejected objects
in orange.

## Correcting the bead outlines by hand

If a QC image shows an outline on something that isn't a good bead, or a good bead that was missed,
you can correct that image's outlines:

1. In Fiji: File > Open..., choose `edit_beads.ijm`, then press Run. It asks for two folders: choose
   the experiment's folder (such as `exp2`) first, then its `results` folder.
2. Pick the image to start with. It opens with every outline shown and numbered, and a window that
   sums up what to do.
   - The colours: cyan for the outlines already there when the image opened (found by
     `bead_segmentation.ijm`, or saved by you before), green for the outlines you add now, and yellow
     for the outline selected. A circle you've drawn is yellow until you press T.
   - To remove an outline: click its number on the image, then press D (or click Delete in the ROI
     Manager).
   - To add a missed bead: zoom in with the + key, drag a circle around the bead with the oval tool
     and press T; it turns green. Draw it on the bead's dark edge, like the other outlines, not around
     the bright halo outside it.
   - Each T adds one bead. An outline with more than one region, one on a bead that already has an
     outline, or one too small or too big to be a bead isn't added, and a message says why.
   - A shows or hides all the outlines, and L their numbers. The C slider under the image switches
     between transmitted light and fluorescence.
3. When the image is done, press N (or the green arrow on the Fiji toolbar): its outlines are saved in
   a `manual_beads` folder inside the experiment's folder, and the next image opens. An image you
   haven't changed isn't saved, so it keeps its automatic outlines.
   - To undo everything you've changed on an image since it opened, press X (or the red cross on the
     toolbar).
   - To stop, close the image: its changes are saved too.
   - To use other keys than N, X, A, L and D, tick "Change the hotkeys" in the first window. Your
     keys are kept for next time.
   - If outlines you add stop turning green, the macro has stopped, and so have its keys and buttons
     (they say so when pressed). Changes since the last Next weren't saved: close the image and run
     the macro again.
4. When you've corrected every image you want to, update the results:
   - Run `bead_segmentation.ijm` again and choose the same two folders as before (`exp2`, then
     `exp2/results`). It sees that the folder already has results and asks what to do: click Update.
   - It measures again only the images whose outlines you've corrected (or whose corrections you've
     deleted) since the results were made, with the same settings as before, and leaves every other
     image's results as they are. For each corrected image it measures your outlines instead of
     finding its own, with no size, shape or focus checks. `segmentation_log.csv` marks those images
     "outlines from manual_beads".
   - Then run `python exp2/analyze.py` and `python exp2/make_figures.py` again.

   You can correct a few images, update, and correct more later: each update only does what changed.

Running `edit_beads.ijm` on an image again starts from your corrected outlines. To go back to the
automatic outlines, delete the image's file from the experiment's `manual_beads` folder, then update
the results as in step 4.

## Adding new images

1. Name each image the same way as the others in its experiment: before or after, the treatment, the
   well and the position. For example, `after_probe-1to1000_W02_3.oir` means after treatment, probe at
   1:1000, well 2, position 3.
   - If you repeat a treatment, give it well numbers that treatment hasn't used before.
   - For a background image, write `background` in place of the position; it is skipped.
2. Put the new images in the experiment's folder.
3. Run all three steps again for that experiment, with a new, empty `results` folder. If a well now has
   more than 3 images at a timepoint, run `select_images.py` as above to keep its best 3.

The new images are added to the results and figures automatically. A treatment word the experiment
hasn't used before needs adding to `GROUPS` in its `settings.py`. `README.md` has the full details of
the analysis.
