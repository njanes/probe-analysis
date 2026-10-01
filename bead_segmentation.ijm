// bead_segmentation.ijm
// Fiji macro: finds the silica beads in each image, saves their outlines, and measures
// probe fluorescence on every bead.
//
// HOW TO RUN
//   Fiji > File > Open... > this file, then press Run (or Plugins > Macros > Run...), and
//   choose the probe-analysis folder when asked.
//   It reads every .oir file in data/ and writes to results/.
//
// WHAT IT DOES, for each image
//   1. Finds beads in the transmitted-light channel: evens out uneven lighting, marks pixels
//      that differ from background, fills and splits touching beads, then keeps round objects
//      of the expected size that don't touch the edge.
//   2. Measures every bead in the fluorescence channel, using the same outlines: whole-bead
//      mean and maximum, edge-ring mean, and the local background around the bead (mean, SD,
//      pixel count), keeping clear of all other objects.
//   3. Saves: bead outlines (results/rois/*.zip, open with the ROI Manager), two QC images
//      (results/qc/*_beads.png on the transmitted-light image, *_probe.png on the fluorescence
//      image; beads kept in cyan, rejected objects in orange), results/figure_images/*_fluor.png
//      (one fixed display range, for figures only), results/bead_measurements.csv (one row per
//      bead) and results/segmentation_log.csv (one row per image).
//
// The .oir files (Olympus FV3000): channel 1 = fluorescence (488 nm), channel 2 = transmitted
// light, one plane, 0.1036 um pixels (6 images at half resolution, 0.2072 um). The beads are
// about 4 um, but in transmitted light each has a bright halo, so the detected outline is about
// 5 um across and the fluorescent ring sits 4-6 px inside it. Hence: keep outlines 3.8-7 um
// wide, then shrink them by 5 px.
//
// Note: this macro turns on Process > Binary > Options > "Black background".

// ---- settings --------------------------------------------------------------
beadChannel = 2;        // transmitted light: beads are found here, so finding them never depends on fluorescence
probeChannel = 1;       // probe fluorescence: measured here
skipText = "Background";  // skip AD_2026.09.24_AP2W9.3Background.oir (not one of the well positions)
minDiam = 3.8;          // keep objects 3.8-7 um wide (outline incl. halo; debris is under 3.2 um)
maxDiam = 7.0;
minCirc = 0.75;         // minimum circularity (1 = perfect circle)
minThreshold = 80;      // lowest allowed Otsu threshold, so noise isn't outlined when there are few beads
// pixel settings, for 0.1036 um pixels; scaled for the half-resolution images
refPixelUm = 0.1036;
shrinkPx = 5;           // shrink outlines to match the fluorescent ring, not the halo
ringWidth = 5;          // edge ring width
bgGap = 4;              // gap between any object and the background band
bgWidth = 10;           // background band width
// figure images: one fixed display range for every image (display only; measurements are unaffected)
figMin = 0;
figMax = 4000;
barUm = 20;             // scale bar

// ---- folders ---------------------------------------------------------------
projectDir = getDirectory("Choose the probe-analysis folder");
dataDir = projectDir + "data" + File.separator;
resultsDir = projectDir + "results" + File.separator;
roiDir = resultsDir + "rois" + File.separator;
qcDir = resultsDir + "qc" + File.separator;
figDir = resultsDir + "figure_images" + File.separator;
File.makeDirectory(roiDir);
File.makeDirectory(qcDir);
File.makeDirectory(figDir);

setBatchMode(true);
setOption("BlackBackground", true);
run("Set Measurements...", "area shape redirect=None decimal=3");
roiManager("reset");
run("Clear Results");
print("\\Clear");

csv = "file,bead,x_px,y_px,area_px,circularity,disc_mean,ring_mean,bg_mean,bg_sd,bg_n,disc_max\n";
logCsv = "file,status,pixel_um,objects_found,beads_kept,threshold\n";

files = getFileList(dataDir);
Array.sort(files);
done = 0;

for (f = 0; f < files.length; f++) {
	name = files[f];
	if (!endsWith(name, ".oir")) continue;
	if (indexOf(name, skipText) >= 0) {
		print("Skipping " + name);
		logCsv = logCsv + name + ",skipped (name filter),,,,\n";
		continue;
	}
	done++;
	base = substring(name, 0, lastIndexOf(name, "."));
	print("[" + done + "] " + name);

	// ---- open the file, and scale the pixel settings to its resolution --------
	run("Bio-Formats Importer", "open=[" + dataDir + name + "] color_mode=Grayscale view=Hyperstack stack_order=XYCZT");
	original = getImageID();
	getPixelSize(unit, pixelUm, ph);                         // microns
	radiusPx = (minDiam + maxDiam) / 4 / pixelUm;           // typical bead radius, pixels
	pf = refPixelUm / pixelUm;                              // 1 = full resolution, 0.5 = half
	if (abs(pf - 1) < 0.05) pf = 1;
	sPx = round(shrinkPx * pf);
	rW = maxOf(1, round(ringWidth * pf));
	gPx = maxOf(1, round(bgGap * pf));
	bW = maxOf(1, round(bgWidth * pf));
	sm = maxOf(0.5, 2 * pf);
	openR = maxOf(1, round(2 * pf));
	closeR = maxOf(1, round(3 * pf));
	minAreaPx = PI * pow(minDiam / pixelUm / 2, 2);
	maxAreaPx = PI * pow(maxDiam / pixelUm / 2, 2);

	// work in pixel units, one window per channel: C1-work, C2-work
	run("Duplicate...", "title=work duplicate");
	run("Set Scale...", "distance=0 known=0 unit=pixel");
	selectImage(original);
	close();
	selectImage("work");
	run("Split Channels");

	// ---- STEP A: find every object in the bead channel ---------------------
	getPlane(beadChannel, "segRaw");
	run("Duplicate...", "title=seg");
	run("32-bit");
	run("Duplicate...", "title=segBG");
	run("Gaussian Blur...", "sigma=" + (4 * radiusPx));   // large-scale lighting
	imageCalculator("Subtract", "seg", "segBG");            // remove uneven lighting
	close("segBG");
	selectImage("seg");
	run("Abs");                                             // beads may look dark OR bright
	run("Gaussian Blur...", "sigma=" + sm);
	// pick the threshold on a copy with the brightest 1% clipped (so specks can't set it),
	// then apply it to the unclipped image
	run("Duplicate...", "title=segClip");
	run("Max...", "value=" + percentile(0.99));
	setAutoThreshold("Otsu dark");
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
	run("Clear Results");

	// ---- STEP B: keep objects that look like single beads ------------------
	roiManager("reset");
	selectImage("allObjects");
	run("Analyze Particles...", "size=" + minAreaPx + "-" + maxAreaPx
		+ " pixel circularity=" + minCirc + "-1.00 show=Nothing exclude add");
	nBeads = roiManager("count");
	print("  " + nBeads + " beads kept of " + nObjects + " objects");

	// objects that were NOT kept, for the orange outlines in the QC images
	selectImage("allObjects");
	run("Duplicate...", "title=rejected");
	setColor(0);
	for (i = 0; i < nBeads; i++) {
		roiManager("select", i);
		run("Enlarge...", "enlarge=1 pixel");
		fill();
	}
	run("Select None");

	// shrink each outline so it matches the bead itself, not the bright halo around it
	selectImage("allObjects");
	for (i = 0; i < nBeads; i++) {
		roiManager("select", i);
		run("Enlarge...", "enlarge=-" + sPx + " pixel");
		roiManager("update");
	}
	run("Select None");

	// pixels within bgGap of ANY object are left out of background measurements
	selectImage("allObjects");
	run("Duplicate...", "title=nearObjects");
	run("Maximum...", "radius=" + gPx);

	// ---- STEP C: measure every bead ----------------------------------------
	getPlane(probeChannel, "probe");
	run("32-bit");
	run("Duplicate...", "title=probeBG");
	selectImage("nearObjects");
	run("Create Selection");
	selectImage("probeBG");
	run("Restore Selection");
	run("Set...", "value=NaN");                             // NaN pixels are ignored in statistics
	selectImage("nearObjects");
	run("Select None");
	selectImage("probeBG");
	run("Select None");

	for (i = 0; i < nBeads; i++) {
		selectImage("probe");
		roiManager("select", i);
		getStatistics(area, discMean, discMin, discMax);
		x = getValue("X");
		y = getValue("Y");
		circ = getValue("Circ.");
		run("Enlarge...", "enlarge=-" + rW + " pixel");
		run("Make Band...", "band=" + rW);                  // inner ring at the bead edge
		getStatistics(ringN, ringMean);

		selectImage("probeBG");
		roiManager("select", i);
		run("Enlarge...", "enlarge=" + (gPx + sPx) + " pixel");
		run("Make Band...", "band=" + bW);                  // ring of background around the bead
		getStatistics(bgN, bgMean, mn, mx, bgSd);
		csv = csv + name + "," + (i + 1) + "," + d2s(x, 1) + "," + d2s(y, 1) + "," + area + ","
			+ d2s(circ, 3) + "," + d2s(discMean, 3) + "," + d2s(ringMean, 3) + "," + d2s(bgMean, 3) + ","
			+ d2s(bgSd, 3) + "," + bgN + "," + discMax + "\n";
	}
	close("probe");
	close("probeBG");

	// ---- STEP D: save outlines and QC images -------------------------------
	roiManager("deselect");
	roiManager("save", roiDir + base + "_RoiSet.zip");
	saveOutlined("segRaw", nBeads, qcDir + base + "_beads.png");
	getPlane(probeChannel, "probeShow");
	saveOutlined("probeShow", nBeads, qcDir + base + "_probe.png");

	// ---- STEP E: figure image (display only; measurements are already done) ----
	getPlane(probeChannel, "figFl");
	saveFigure("figFl", pixelUm, figMin, figMax, barUm, figDir + base + "_fluor.png");

	logCsv = logCsv + name + ",ok," + d2s(pixelUm, 4) + "," + nObjects + "," + nBeads + "," + d2s(lower, 2) + "\n";
	run("Close All");
	roiManager("reset");
}

File.saveString(csv, resultsDir + "bead_measurements.csv");
File.saveString(logCsv, resultsDir + "segmentation_log.csv");
setBatchMode(false);
print("Done: " + done + " file(s). Results in " + resultsDir);


// ======================= helper functions =================================

// Copy channel c (from the split channel windows) into a new image.
function getPlane(c, newTitle) {
	selectImage("C" + c + "-work");
	run("Duplicate...", "title=" + newTitle);
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

// Save a fluorescence figure PNG: fixed linear display range (the same for every image),
// intensity bar and scale bar. Display only.
function saveFigure(title, pixelUm, dMin, dMax, barUm, path) {
	selectImage(title);
	run("Properties...", "channels=1 slices=1 frames=1 pixel_width=" + pixelUm + " pixel_height="
		+ pixelUm + " voxel_depth=1 unit=micron");               // restore calibration for the scale bar
	run("Grays");
	setMinAndMax(dMin, dMax);
	scale = getWidth() / 512;
	run("Scale Bar...", "width=" + barUm + " height=" + barUm + " thickness=" + round(5 * scale)
		+ " font=" + round(14 * scale) + " color=White background=None location=[Lower Right] horizontal bold overlay");
	run("Calibration Bar...", "location=[Upper Right] fill=None label=White number=3 decimal=0 font=12 zoom="
		+ scale + " bold overlay");
	run("Flatten");
	saveAs("PNG", path);
	close();
	close(title);
}

// Save a contrast-stretched PNG: kept beads outlined cyan, rejected objects orange.
function saveOutlined(title, nBeads, path) {
	selectImage("rejected");
	run("Create Selection");
	selectImage(title);
	run("Select None");
	run("Enhance Contrast", "saturated=0.01");
	run("Restore Selection");
	Overlay.addSelection("orange", 2);
	run("Select None");
	for (k = 0; k < nBeads; k++) {
		roiManager("select", k);
		Overlay.addSelection("cyan", 2);
	}
	run("Select None");
	run("Flatten");
	saveAs("PNG", path);
	close();
}
