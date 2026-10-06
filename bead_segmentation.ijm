// bead_segmentation.ijm
// Fiji macro: finds silica beads, saves their outlines, and measures probe
// fluorescence on every bead.
//
// HOW TO RUN
//   Fiji > File > Open... > this file, then press Run (or Plugins > Macros > Run...).
//   It asks for the image folder, then an output folder, then shows the settings.
//   Tip: set "Process only the first N files" to 2 or 3, check the QC images,
//   adjust, then run everything with 0.
//
// WHAT IT DOES, for each image file in the folder
//   1. Opens it with Bio-Formats (.oir, .czi, .lif, .nd2) or natively (.tif).
//   2. Finds beads in the chosen channel and frame: evens out uneven lighting,
//      marks pixels that differ from background, fills and splits touching beads,
//      then keeps round objects of the expected size that don't touch the edge and
//      are in focus in the transmitted-light image: beads above or below the focal
//      plane have a bright (or dark) centre, and smeared blurs have soft edges. In a
//      confocal image those beads look dim whether or not probe is bound, so they are left out.
//   3. Measures every bead in the probe channel in EVERY time frame, using the
//      same outlines: whole-bead mean, edge-ring mean, and the local background
//      around the bead (mean, SD, pixel count), keeping clear of all other objects.
//   4. Saves: bead outlines (rois/*.zip, open with the ROI Manager), two QC images
//      per file (qc/*_beads.png on the transmitted-light image, qc/*_probe.png on
//      the fluorescence image; beads kept in cyan, rejected objects in orange,
//      out-of-focus beads in magenta),
//      figure_images/*_fluor.png (fixed display range, for figures only),
//      bead_measurements.csv (one row per bead per frame), segmentation_log.csv
//      (one row per file) and settings_used.txt.
//
// No transmitted-light channel? Set "Channel to find beads in" to the probe
// channel and "Frame to find beads in" to the frame AFTER treatment. Beads that
// did not bind will then be invisible and missed, which biases results upward. Also set the
// three out-of-focus checks to 0, because they are designed for transmitted light.
//
// Your FV3000 .oir files: channel 1 = CH1 fluorescence (488 nm, EGFP settings),
// channel 2 = transmitted light, one timepoint, no z-stack, 0.1036 um pixels.
// The beads are about 4 um, but in transmitted light each has a bright halo, so the
// detected outline is about 5 um across (radius 23-27 px) and the fluorescent ring
// sits 4-6 px inside it. Hence the defaults: keep outlines 3.8-7 um wide, shrink 5 px.
//
// Note: this macro turns on Process > Binary > Options > "Black background".

// ---- settings: two folder pickers, then one dialog ------------------------
inputDir = stripSlash(getDirectory("Choose the folder with your images"));
outputDir = stripSlash(getDirectory("Choose an EMPTY folder for the results"));

Dialog.create("Bead segmentation settings");
Dialog.addString("File extension", ".oir");
Dialog.addString("Skip files whose name contains (blank = none)", "Background", 20);
Dialog.addNumber("Process only the first N files (0 = all)", 0);
Dialog.addNumber("Channel to find beads in (transmitted light)", 2);
Dialog.addNumber("Probe fluorescence channel", 1);
Dialog.addNumber("Frame to find beads in (1 = first)", 1);
Dialog.addNumber("Z slice if z-stack (0 = max projection)", 0);
Dialog.addNumber("Pixel size in microns (0 = read from file)", 0);
Dialog.addMessage("Size range of bead outlines in the transmitted-light image (incl. halo).\nYour beads measure 4.1-6.3 um this way; debris is under 3.2 um.");
Dialog.addNumber("Keep objects at least this wide (microns)", 3.8);
Dialog.addNumber("Keep objects at most this wide (microns)", 7.0);
Dialog.addNumber("Minimum circularity (1 = perfect circle)", 0.75);
Dialog.addMessage("Out-of-focus beads (transmitted light; 0 = check off)");
Dialog.addNumber("Maximum centre contrast (bright or dark centre = above or below focus)", 0.2);
Dialog.addNumber("Maximum bright spot in the centre (catches blurred beads the above misses)", 0.35);
Dialog.addNumber("Minimum edge sharpness (soft edges = smeared blur)", 0.09);
Dialog.addNumber("Shrink outlines before measuring (pixels)", 5);
Dialog.addChoice("Threshold method", newArray("Otsu", "Triangle", "Li", "Huang", "Default"), "Otsu");
Dialog.addNumber("Lowest allowed threshold (stops noise being outlined when few beads)", 80);
Dialog.addNumber("Edge ring width (pixels)", 5);
Dialog.addNumber("Gap between objects and background (pixels)", 4);
Dialog.addNumber("Background ring width (pixels)", 10);
Dialog.addNumber("Minimum background pixels per bead", 50);
Dialog.addNumber("Pixel settings above are for pixels of (microns; scaled for other resolutions)", 0.1036);
Dialog.addMessage("Figure images: fluorescence saved with ONE fixed display range for every image\n(display only; pixel values and measurements are not affected)");
Dialog.addCheckbox("Export figure images", true);
Dialog.addNumber("Display minimum (counts)", 0);
Dialog.addNumber("Display maximum (counts)", 4000);
Dialog.addChoice("Figure colour", newArray("Grays", "Green", "Fire"), "Grays");
Dialog.addNumber("Scale bar (microns, 0 = none)", 20);
Dialog.addCheckbox("Also export transmitted-light figure images", false);
Dialog.show();
fileExt = Dialog.getString();
skipText = Dialog.getString();
maxFiles = Dialog.getNumber();
segChannel = Dialog.getNumber();
probeChannel = Dialog.getNumber();
segFrame = Dialog.getNumber();
zSlice = Dialog.getNumber();
pixelSizeOverride = Dialog.getNumber();
minDiam = Dialog.getNumber();
maxDiam = Dialog.getNumber();
minCirc = Dialog.getNumber();
maxCC = Dialog.getNumber();
maxSpot = Dialog.getNumber();
minSharp = Dialog.getNumber();
shrinkPx = Dialog.getNumber();
minThreshold = Dialog.getNumber();
thresholdMethod = Dialog.getChoice();
ringWidth = Dialog.getNumber();
bgGap = Dialog.getNumber();
bgWidth = Dialog.getNumber();
minBgPixels = Dialog.getNumber();
refPixelUm = Dialog.getNumber();
exportFig = Dialog.getCheckbox();
figMin = Dialog.getNumber();
figMax = Dialog.getNumber();
figLut = Dialog.getChoice();
barUm = Dialog.getNumber();
exportTL = Dialog.getCheckbox();

setBatchMode(true);
setOption("BlackBackground", true);
run("Set Measurements...", "area shape redirect=None decimal=3");
roiManager("reset");
run("Clear Results");
print("\\Clear");

sep = File.separator;
roiDir = outputDir + sep + "rois";
qcDir = outputDir + sep + "qc";
figDir = outputDir + sep + "figure_images";
File.makeDirectory(roiDir);
File.makeDirectory(qcDir);
if (exportFig) File.makeDirectory(figDir);

csv = "file,frame,bead,x_px,y_px,area_px,circularity,disc_mean,ring_mean,bg_mean,bg_sd,bg_n,bg_source,image_bg_mean,image_bg_sd,disc_max,edge_sharpness,centre_contrast,bright_spot\n";
logCsv = "file,status,channels,z_slices,frames,pixel_um,bead_radius_px,objects_found,beads_kept,threshold,out_of_focus\n";

files = getFileList(inputDir);
Array.sort(files);
done = 0;

for (f = 0; f < files.length; f++) {
	name = files[f];
	if (!endsWith(toLowerCase(name), toLowerCase(fileExt))) continue;
	if (skipText != "" && indexOf(name, skipText) >= 0) {
		print("Skipping " + name);
		logCsv = logCsv + name + ",skipped (name filter),,,,,,,,\n";
		continue;
	}
	if (maxFiles > 0 && done >= maxFiles) break;
	done++;
	base = substring(name, 0, lastIndexOf(name, "."));
	print("[" + done + "] " + name);

	// ---- open and check the file ------------------------------------------
	openImage(inputDir + sep + name);
	original = getImageID();
	getDimensions(w, h, nC, nZ, nT);
	getPixelSize(unit, pw, ph);
	pixelUm = toMicrons(pw, unit);
	if (pixelSizeOverride > 0) pixelUm = pixelSizeOverride;
	dims = "" + nC + "," + nZ + "," + nT;

	problem = "";
	if (isNaN(pixelUm) || pixelUm <= 0) problem = "no pixel size in file: set it in the dialog";
	if (segChannel > nC || probeChannel > nC) problem = "file has only " + nC + " channel(s)";
	if (segFrame > nT) problem = "file has only " + nT + " frame(s)";
	if (problem != "") {
		print("  SKIPPED: " + problem);
		logCsv = logCsv + name + ",skipped (" + problem + ")," + dims + ",,,,,\n";
		run("Close All");
		continue;
	}
	radiusPx = (minDiam + maxDiam) / 4 / pixelUm;           // typical bead radius, pixels
	// pixel-based settings are defined at refPixelUm; scale them for this image's resolution
	pf = refPixelUm / pixelUm;                              // 1 = full resolution, 0.5 = half
	if (abs(pf - 1) < 0.05) pf = 1;
	sPx = round(shrinkPx * pf);
	rW = maxOf(1, round(ringWidth * pf));
	gPx = maxOf(1, round(bgGap * pf));
	bW = maxOf(1, round(bgWidth * pf));
	mBg = minBgPixels * pf * pf;
	sm = maxOf(0.5, 2 * pf);
	openR = maxOf(1, round(2 * pf));
	closeR = maxOf(1, round(3 * pf));
	if (pf != 1) print("  resolution differs from " + refPixelUm + " um: pixel settings scaled by " + d2s(pf, 2));
	minAreaPx = PI * pow(minDiam / pixelUm / 2, 2);
	maxAreaPx = PI * pow(maxDiam / pixelUm / 2, 2);
	print("  pixel size " + d2s(pixelUm, 4) + " um; keeping round objects " + d2s(minDiam / pixelUm, 0)
		+ "-" + d2s(maxDiam / pixelUm, 0) + " px across");

	// ---- reduce a z-stack to one plane, then work in pixel units -----------
	selectImage(original);
	if (nZ > 1 && zSlice == 0) {
		run("Z Project...", "projection=[Max Intensity] all");
	} else if (nZ > 1) {
		if (Stack.isHyperstack) run("Duplicate...", "title=zsel duplicate slices=" + zSlice);
		else run("Duplicate...", "title=zsel duplicate range=" + zSlice + "-" + zSlice);
	} else {
		run("Duplicate...", "title=work duplicate");
	}
	rename("work");
	run("Set Scale...", "distance=0 known=0 unit=pixel");
	selectImage(original);
	close();
	selectImage("work");
	if (nC > 1) run("Split Channels");                     // one window per channel: C1-work, C2-work
	else rename("C1-work");

	// ---- STEP A: find every object in the bead channel ---------------------
	getPlane(segChannel, segFrame, "segRaw");
	run("Duplicate...", "title=seg");
	run("32-bit");
	run("Duplicate...", "title=segBG");
	run("Gaussian Blur...", "sigma=" + (4 * radiusPx));   // large-scale lighting
	imageCalculator("Subtract", "seg", "segBG");            // remove uneven lighting
	selectImage("segBG");
	rename("light");                                        // kept: local light level, for the focus checks
	selectImage("seg");
	run("Abs");                                             // beads may look dark OR bright
	run("Gaussian Blur...", "sigma=" + sm);
	// pick the threshold on a copy with the brightest 1% clipped (so specks can't set it),
	// then apply it to the unclipped image
	run("Duplicate...", "title=segClip");
	run("Max...", "value=" + percentile(0.99));
	setAutoThreshold(thresholdMethod + " dark");
	getThreshold(lower, upper);
	close("segClip");
	if (lower < minThreshold) {                             // few beads: automatic threshold
		lower = minThreshold;                               // falls to noise level, so use
		print("  threshold raised to the floor (" + minThreshold + "): few beads in this image");
	}
	selectImage("seg");
	setThreshold(lower, 1e30);
	run("Convert to Mask");
	run("Maximum...", "radius=" + closeR);                  // closing: seal gaps in bead edges
	run("Minimum...", "radius=" + closeR);                  // so "C" shapes fill in as discs
	run("Fill Holes");
	run("Minimum...", "radius=" + openR);                   // opening: removes specks
	run("Maximum...", "radius=" + openR);                   // and thin bridges
	run("Watershed");                                       // split touching beads
	rename("allObjects");
	run("Analyze Particles...", "size=0-Infinity pixel show=Nothing display clear");
	nObjects = nResults;
	// report the sizes of round objects, so a wrong size range is easy to spot
	roundDiams = newArray(0);
	for (k = 0; k < nResults; k++) {
		d = 2 * sqrt(getResult("Area", k) / PI) * pixelUm;
		if (getResult("Circ.", k) >= minCirc && d > 2) roundDiams = Array.concat(roundDiams, d);
	}
	if (roundDiams.length > 0) {
		Array.getStatistics(roundDiams, dMin, dMax, dMean);
		Array.sort(roundDiams);
		print("  round objects wider than 2 um: " + roundDiams.length + ", widths " + d2s(dMin, 1) + "-"
			+ d2s(dMax, 1) + " um (median " + d2s(roundDiams[floor(roundDiams.length / 2)], 1) + ")");
	}
	run("Clear Results");

	// ---- STEP B: keep objects that look like single beads ------------------
	roiManager("reset");
	selectImage("allObjects");
	run("Analyze Particles...", "size=" + minAreaPx + "-" + maxAreaPx
		+ " pixel circularity=" + minCirc + "-1.00 show=Nothing exclude add");
	nCand = roiManager("count");

	// objects of the wrong size or shape, for the orange outlines in the QC images
	selectImage("allObjects");
	run("Duplicate...", "title=rejected");
	setColor(0);
	for (i = 0; i < nCand; i++) {
		roiManager("select", i);
		run("Enlarge...", "enlarge=1 pixel");
		fill();
	}
	run("Select None");

	// focus checks on the transmitted-light image (never the fluorescence):
	//   centre contrast = (centre brightness - local light level) / local light level. In focus, a
	//     bead's centre looks like the background (about 0); above or below the focal plane it acts
	//     as a small lens and its centre turns bright (or dark).
	//   bright spot = brightest part (95th percentile) of the inner 60% of the bead, relative to the
	//     local light level: catches out-of-focus beads whose bright spot is small or off-centre.
	//   edge sharpness = mean intensity gradient over the bead and its rim, relative to the local
	//     light level, per micron. Smeared blurs have soft edges and low values.
	selectImage("segRaw");
	run("Duplicate...", "title=edges");
	run("32-bit");
	run("Gaussian Blur...", "sigma=" + sm);                 // suppress pixel noise first
	run("Find Edges");                                      // Sobel gradient magnitude
	selectImage("segRaw");
	run("Duplicate...", "title=tlSmooth");
	run("32-bit");
	run("Gaussian Blur...", "sigma=" + sm);
	eW = maxOf(1, round(3 * pf));
	sharp = newArray(nCand);
	cc = newArray(nCand);
	spot = newArray(nCand);
	for (i = 0; i < nCand; i++) {
		sharp[i] = edgeSharpness(i, eW, pixelUm);
		cc[i] = centreContrast(i, sPx);
		spot[i] = brightSpot(i, sPx);
	}
	close("edges");
	close("tlSmooth");

	// remove out-of-focus beads (magenta in the QC images)
	selectImage("allObjects");
	run("Duplicate...", "title=blurry");
	run("Select All");
	setColor(0);
	fill();
	run("Select None");
	nBlurry = 0;
	keptSharp = newArray(0);
	keptCC = newArray(0);
	keptSpot = newArray(0);
	for (i = nCand - 1; i >= 0; i--) {
		blurred = (minSharp > 0 && sharp[i] < minSharp) || (maxCC > 0 && abs(cc[i]) > maxCC)
			|| (maxSpot > 0 && spot[i] > maxSpot);
		if (blurred) {
			selectImage("blurry");
			roiManager("select", i);
			run("Enlarge...", "enlarge=1 pixel");
			setColor(255);
			fill();
			roiManager("select", i);
			roiManager("delete");
			nBlurry++;
		} else {
			keptSharp = Array.concat(sharp[i], keptSharp);  // same order as the ROIs
			keptCC = Array.concat(cc[i], keptCC);
			keptSpot = Array.concat(spot[i], keptSpot);
		}
	}
	selectImage("blurry");
	run("Select None");
	nBeads = roiManager("count");
	print("  " + nBeads + " beads kept of " + nObjects + " objects (" + nBlurry + " out of focus)");

	// shrink each outline so it matches the bead itself, not the bright halo around it
	if (sPx > 0) {
		selectImage("allObjects");
		for (i = 0; i < nBeads; i++) {
			roiManager("select", i);
			run("Enlarge...", "enlarge=-" + sPx + " pixel");
			roiManager("update");
		}
		run("Select None");
	}

	// pixels within bgGap of ANY object are left out of background measurements
	selectImage("allObjects");
	run("Duplicate...", "title=nearObjects");
	run("Maximum...", "radius=" + gPx);

	// ---- STEP C: measure every bead in every frame -------------------------
	for (t = 1; t <= nT; t++) {
		getPlane(probeChannel, t, "probe");
		run("32-bit");
		run("Duplicate...", "title=probeBG");
		selectImage("nearObjects");
		run("Create Selection");
		if (selectionType() != -1) {
			selectImage("probeBG");
			run("Restore Selection");
			run("Set...", "value=NaN");                     // NaN pixels are ignored in statistics
		}
		selectImage("nearObjects");
		run("Select None");
		selectImage("probeBG");
		run("Select None");
		getStatistics(imgBgN, imgBgMean, mn, mx, imgBgSd);  // whole-image background

		for (i = 0; i < nBeads; i++) {
			selectImage("probe");
			roiManager("select", i);
			getStatistics(area, discMean, discMin, discMax);
			x = getValue("X");
			y = getValue("Y");
			circ = getValue("Circ.");
			ringMean = NaN;
			run("Enlarge...", "enlarge=-" + rW + " pixel");
			if (selectionType() != -1) {
				run("Make Band...", "band=" + rW);          // inner ring at the bead edge
				getStatistics(ringN, ringMean);
			}

			selectImage("probeBG");
			roiManager("select", i);
			run("Enlarge...", "enlarge=" + (gPx + sPx) + " pixel");
			run("Make Band...", "band=" + bW);              // ring of background around the bead
			getStatistics(bgN, bgMean, mn, mx, bgSd);
			bgSource = "local";
			if (bgN < mBg) {                                // crowded: use whole-image background
				bgMean = imgBgMean;
				bgSd = imgBgSd;
				bgSource = "image";
			}
			csv = csv + name + "," + t + "," + (i + 1) + "," + d2s(x, 1) + "," + d2s(y, 1) + ","
				+ area + "," + d2s(circ, 3) + "," + d2s(discMean, 3) + "," + d2s(ringMean, 3) + ","
				+ d2s(bgMean, 3) + "," + d2s(bgSd, 3) + "," + bgN + "," + bgSource + ","
				+ d2s(imgBgMean, 3) + "," + d2s(imgBgSd, 3) + "," + discMax + "," + d2s(keptSharp[i], 4) + "," + d2s(keptCC[i], 4) + "," + d2s(keptSpot[i], 4) + "\n";
		}
		close("probe");
		close("probeBG");
	}

	// ---- STEP D: save outlines and a QC image ------------------------------
	if (nBeads > 0) {
		roiManager("deselect");
		roiManager("save", roiDir + sep + base + "_RoiSet.zip");
	}
	saveOutlined("segRaw", nBeads, qcDir + sep + base + "_beads.png");
	getPlane(probeChannel, nT, "probeShow");
	saveOutlined("probeShow", nBeads, qcDir + sep + base + "_probe.png");

	// ---- STEP E: figure images (display only; measurements are already done) ----
	if (exportFig) {
		getPlane(probeChannel, nT, "figFl");
		saveFigure("figFl", figLut, figMin, figMax, true, pixelUm, barUm, figDir + sep + base + "_fluor.png");
		if (exportTL && segChannel != probeChannel) {
			getPlane(segChannel, segFrame, "figTl");
			saveFigure("figTl", "Grays", 0, 0, false, pixelUm, barUm, figDir + sep + base + "_transmitted.png");
		}
	}

	logCsv = logCsv + name + ",ok," + dims + "," + d2s(pixelUm, 4) + "," + d2s(radiusPx, 1) + ","
		+ nObjects + "," + nBeads + "," + d2s(lower, 2) + "," + nBlurry + "\n";
	run("Close All");
	roiManager("reset");
}

File.saveString(csv, outputDir + sep + "bead_measurements.csv");
File.saveString(logCsv, outputDir + sep + "segmentation_log.csv");
settings = "inputDir=" + inputDir + "\nfileExt=" + fileExt + "\nskipText=" + skipText
	+ "\nsegChannel=" + segChannel + "\nprobeChannel=" + probeChannel + "\nsegFrame=" + segFrame
	+ "\nzSlice=" + zSlice + "\nminDiam=" + minDiam + "\nmaxDiam=" + maxDiam + "\npixelSizeOverride=" + pixelSizeOverride
	+ "\nshrinkPx=" + shrinkPx + "\nminThreshold=" + minThreshold + "\nminCirc=" + minCirc + "\nmaxCentreContrast=" + maxCC + "\nmaxBrightSpot=" + maxSpot + "\nminEdgeSharpness=" + minSharp
	+ "\nthresholdMethod=" + thresholdMethod + "\nringWidth=" + ringWidth + "\nbgGap=" + bgGap
	+ "\nbgWidth=" + bgWidth + "\nminBgPixels=" + minBgPixels + "\nrefPixelUm=" + refPixelUm + "\n";
if (exportFig) settings = settings + "figure display range=" + figMin + "-" + figMax + " (" + figLut
	+ ", linear, identical for all images)\nscale bar=" + barUm + " um\n";
File.saveString(settings, outputDir + sep + "settings_used.txt");
setBatchMode(false);
print("Done: " + done + " file(s). Results in " + outputDir);


// ======================= helper functions =================================

function openImage(path) {
	lower = toLowerCase(path);
	if (endsWith(lower, ".tif") || endsWith(lower, ".tiff")) {
		open(path);
	} else {
		run("Bio-Formats Importer", "open=[" + path + "] color_mode=Grayscale view=Hyperstack stack_order=XYCZT");
	}
}

function toMicrons(value, unit) {
	u = toLowerCase(unit);
	if (u == "pixel" || u == "pixels" || u == "") return NaN;
	if (u == "nm" || u == "nanometer" || u == "nanometers") return value / 1000;
	if (u == "mm") return value * 1000;
	return value;                                           // micron, microns, um
}

// Copy one time frame of channel c (from the split channel windows) into a new image.
function getPlane(c, t, newTitle) {
	selectImage("C" + c + "-work");
	if (nSlices == 1) run("Duplicate...", "title=" + newTitle);
	else if (Stack.isHyperstack) run("Duplicate...", "title=" + newTitle + " duplicate frames=" + t);
	else run("Duplicate...", "title=" + newTitle + " duplicate range=" + t + "-" + t);
}

// Value below which fraction p of the current image's pixels fall.
function percentile(p) {
	nBins = 4096;
	getHistogram(values, counts, nBins);
	total = 0;
	for (k = 0; k < nBins; k++) total += counts[k];
	cum = 0;
	for (k = 0; k < nBins; k++) {
		cum += counts[k];
		if (cum >= p * total) return values[k];
	}
	return values[nBins - 1];
}

// Save a figure PNG. Fluorescence: fixed linear display range (the same for every image),
// intensity bar and scale bar. Transmitted light: contrast set per image. Display only.
function saveFigure(title, lut, dMin, dMax, fixedRange, pixelUm, barUm, path) {
	selectImage(title);
	run("Properties...", "channels=1 slices=1 frames=1 pixel_width=" + pixelUm + " pixel_height="
		+ pixelUm + " voxel_depth=1 unit=micron");               // restore calibration for the scale bar
	run(lut);
	if (fixedRange) setMinAndMax(dMin, dMax);
	else run("Enhance Contrast", "saturated=0.35");
	scale = getWidth() / 512;
	if (barUm > 0)
		run("Scale Bar...", "width=" + barUm + " height=" + barUm + " thickness=" + round(5 * scale)
			+ " font=" + round(14 * scale) + " color=White background=None location=[Lower Right] horizontal bold overlay");
	if (fixedRange)
		run("Calibration Bar...", "location=[Upper Right] fill=None label=White number=3 decimal=0 font=12 zoom="
			+ scale + " bold overlay");
	run("Flatten");
	saveAs("PNG", path);
	close();
	close(title);
}

// Save a contrast-stretched PNG: kept beads outlined cyan, rejected objects orange,
// out-of-focus beads magenta.
function saveOutlined(title, nBeads, path) {
	selectImage("rejected");
	run("Create Selection");
	hasObjects = selectionType() != -1;
	selectImage(title);
	run("Select None");
	run("Enhance Contrast", "saturated=0.01");
	if (hasObjects) {
		run("Restore Selection");
		Overlay.addSelection("orange", 2);
		run("Select None");
	}
	selectImage("blurry");
	run("Create Selection");
	hasBlurry = selectionType() != -1;
	selectImage(title);
	if (hasBlurry) {
		run("Restore Selection");
		Overlay.addSelection("magenta", 2);
		run("Select None");
	}
	for (k = 0; k < nBeads; k++) {
		roiManager("select", k);
		Overlay.addSelection("cyan", 2);
	}
	run("Select None");
	run("Flatten");
	saveAs("PNG", path);
	close();
}

// Edge sharpness of ROI i: mean Sobel gradient over the bead plus a rim of eW pixels, divided by 8
// (Sobel scale) and by the local light level, per micron. Needs the "edges" and "light" images.
function edgeSharpness(i, eW, pixelUm) {
	selectImage("light");
	roiManager("select", i);
	getStatistics(nL, level);
	selectImage("edges");
	roiManager("select", i);
	run("Enlarge...", "enlarge=" + eW + " pixel");
	getStatistics(nE, gMean);
	run("Select None");
	selectImage("light");
	run("Select None");
	if (level <= 0) return NaN;
	return gMean / 8 / level / pixelUm;
}

// Centre contrast of ROI i: mean brightness of the central disc (40% of the bead radius, the
// bead being the outline minus its halo of sPx pixels) relative to the local light level.
// About 0 in focus; positive (bright centre) or negative (dark centre) above or below focus.
function centreContrast(i, sPx) {
	selectImage("segRaw");
	roiManager("select", i);
	x = getValue("X");
	y = getValue("Y");
	rc = 0.4 * (sqrt(getValue("Area") / PI) - sPx);
	run("Select None");
	if (rc < 1) return NaN;
	makeOval(x - rc, y - rc, 2 * rc, 2 * rc);
	getStatistics(nC, centre);
	run("Select None");
	selectImage("light");
	level = getPixel(round(x), round(y));
	if (level <= 0) return NaN;
	return (centre - level) / level;
}

// Bright spot of ROI i: 95th percentile of the smoothed transmitted-light image over the inner
// 60% of the bead radius, relative to the local light level. Needs "tlSmooth" and "light".
function brightSpot(i, sPx) {
	selectImage("tlSmooth");
	roiManager("select", i);
	x = getValue("X");
	y = getValue("Y");
	r = 0.6 * (sqrt(getValue("Area") / PI) - sPx);
	run("Select None");
	if (r < 1) return NaN;
	makeOval(x - r, y - r, 2 * r, 2 * r);
	p95 = selectionPercentile(0.95);
	run("Select None");
	selectImage("light");
	level = getPixel(round(x), round(y));
	if (level <= 0) return NaN;
	return (p95 - level) / level;
}

// Value below which fraction p of the pixels in the current selection fall.
function selectionPercentile(p) {
	nBins = 512;
	getHistogram(values, counts, nBins);
	total = 0;
	for (k = 0; k < nBins; k++) total += counts[k];
	cum = 0;
	for (k = 0; k < nBins; k++) {
		cum += counts[k];
		if (cum >= p * total) return values[k];
	}
	return values[nBins - 1];
}

// Remove a trailing / or \ from a folder path.
function stripSlash(path) {
	while (endsWith(path, "/") || endsWith(path, "\\")) path = substring(path, 0, lengthOf(path) - 1);
	return path;
}
