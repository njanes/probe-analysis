// edit_beads.ijm
// Fiji macro: correct the bead outlines from bead_segmentation.ijm by hand.
//
// HOW TO USE
//   1. Run bead_segmentation.ijm as usual and look through its QC images (results/qc).
//   2. Run this macro. It asks for the experiment folder (with the images) and its results folder,
//      then which image to correct, and opens it with its bead outlines in cyan. Remove wrong
//      outlines, and add missed beads one at a time with the oval tool and T: each one added
//      turns green. Each change is saved, in a "manual_beads" folder inside the experiment folder.
//      Close the image when done, and it offers the next image.
//   3. Run bead_segmentation.ijm again, choosing the same results folder, and click Update: it
//      measures again only the images whose outlines you corrected since, using your outlines
//      instead of finding its own. Then run analyze.py and make_figures.py as usual.
// Running this macro again on an image starts from its saved outlines (all cyan then). To go
// back to the automatic outlines, delete the image's file from manual_beads.

var FOUND = "cyan";     // outlines already there when the image opens (found by the macro, or saved before)
var ADDED = "green";    // outlines added while the image is open
var HELP = "How to correct the outlines";

inputDir = stripSlash(getDirectory("Choose the experiment folder (with the images)"));
outputDir = stripSlash(getDirectory("Choose its results folder"));
sep = File.separator;
if (!File.exists(outputDir + sep + "settings_used.txt")
		&& File.exists(outputDir + sep + "results" + sep + "settings_used.txt"))
	outputDir = outputDir + sep + "results";                    // the experiment folder was chosen: use its results
manualDir = inputDir + sep + "manual_beads";
if (!File.exists(outputDir + sep + "settings_used.txt"))
	exit("No settings_used.txt in " + outputDir + ".\nChoose the results folder of a bead_segmentation.ijm run.");
List.setList(File.openAsString(outputDir + sep + "settings_used.txt"));
fileExt = List.get("fileExt");
segChannel = parseInt(List.get("segChannel"));
minDiam = parseFloat(List.get("minDiam"));
maxDiam = parseFloat(List.get("maxDiam"));

all = getFileList(inputDir);
Array.sort(all);
images = newArray(0);
for (k = 0; k < all.length; k++)
	if (endsWith(toLowerCase(all[k]), toLowerCase(fileExt))) images = Array.concat(images, all[k]);
if (images.length == 0) exit("No " + fileExt + " files in " + inputDir);

next = 0;
more = true;
while (more) {
	Dialog.create("Correct bead outlines");
	Dialog.addChoice("Image", images, images[next]);
	Dialog.show();
	name = Dialog.getChoice();
	for (k = 0; k < images.length; k++) if (images[k] == name) next = minOf(k + 1, images.length - 1);
	base = substring(name, 0, lastIndexOf(name, "."));
	manualZip = manualDir + sep + base + "_RoiSet.zip";
	autoZip = outputDir + sep + "rois" + sep + base + "_RoiSet.zip";

	openImage(inputDir + sep + name);
	image = getImageID();
	getDimensions(w, h, nC, nZ, nT);
	getPixelSize(unit, pw, ph);
	um = pw;                                                    // microns per pixel; NaN if not calibrated
	if (unit == "pixels" || unit == "pixel" || unit == "") um = NaN;
	for (c = 1; c <= nC; c++) {
		if (nC > 1) Stack.setChannel(c);
		run("Enhance Contrast", "saturated=0.35");
	}
	if (nC > 1) Stack.setChannel(minOf(segChannel, nC));          // start on transmitted light
	setOption("Changes", false);                                // only the display changed: closing won't ask to save
	roiManager("reset");
	if (File.exists(manualZip)) roiManager("open", manualZip);   // corrected before: continue from there
	else if (File.exists(autoZip)) roiManager("open", autoZip);
	for (i = 0; i < roiManager("count"); i++) {
		roiManager("select", i);
		roiManager("Set Color", FOUND);
	}
	run("Select None");
	roiManager("Show All with labels");
	setTool("oval");
	showHelp(name, image);

	// Until the image is closed: check each outline added with T as it arrives and colour it, and save
	// after every change, so nothing is lost if the macro is stopped (Esc on the image can stop it)
	n = roiManager("count");
	while (isOpen(image)) {
		wait(150);
		c = roiManager("count");
		if (c != n && isOpen(image)) {
			selectImage(image);
			for (k = c - 1; k >= n; k--) check(k, um, minDiam, maxDiam);
			run("Select None");
			if (roiManager("count") != n && roiManager("count") > 0) saveOutlines(manualDir, manualZip);
		}
		n = roiManager("count");
	}

	n = roiManager("count");
	if (n == 0) {
		msg = "No outlines left, so nothing was saved for " + name
			+ ".\nTo leave this image out, add it to EXCLUDE in settings.py.";
	} else {
		saveOutlines(manualDir, manualZip);
		msg = "Saved " + n + " bead outlines for " + name + ".";
	}
	roiManager("reset");
	more = getBoolean(msg + "\n \nCorrect another image?");
}
if (isOpen(HELP)) {
	selectWindow(HELP);
	run("Close");
}
print("To measure the corrected outlines, run bead_segmentation.ijm again into the same results folder and click Update.");


// An outline just added (number k) is kept, in the added colour, if it is one region the size of a
// bead on a bead without an outline; otherwise it is removed again, with a message saying why.
function check(k, um, minDiam, maxDiam) {
	roiManager("select", k);
	getSelectionBounds(x, y, w, h);
	why = "";
	if (selectionType() == 9) why = "it has more than one region. Draw one circle per bead, then press T";
	else if (selectionType() > 4) why = "it isn't an area. Draw a circle around the bead with the oval tool";
	else if (minOf(w, h) * um < minDiam / 2) why = "it is too small to be a bead";
	else if (maxOf(w, h) * um > 2 * maxDiam) why = "it is too big to be one bead";
	else {
		for (i = 0; i < roiManager("count"); i++) {
			if (i == k) continue;
			roiManager("select", i);
			getSelectionBounds(xi, yi, wi, hi);
			d = sqrt(pow(x + w / 2 - xi - wi / 2, 2) + pow(y + h / 2 - yi - hi / 2, 2));
			if (d < (w + h + wi + hi) / 8) {                    // centres closer than half the two radii
				why = "bead " + (i + 1) + " already has an outline";
				break;
			}
		}
	}
	roiManager("select", k);
	if (why != "") {
		roiManager("delete");
		run("Select None");
		showMessage("Outline not added", "That outline wasn't added: " + why + ".");
	} else {
		roiManager("Remove Channel Info");                       // shown on every channel
		roiManager("Remove Slice Info");
		roiManager("Remove Frame Info");
		roiManager("Set Color", ADDED);
	}
}

function saveOutlines(manualDir, manualZip) {
	roiManager("deselect");
	roiManager("Remove Channel Info");                           // outlines apply to every channel,
	roiManager("Remove Slice Info");                             // slice and frame
	roiManager("Remove Frame Info");
	File.makeDirectory(manualDir);
	roiManager("save", manualZip);
}

// The instructions, in a window to the right of the image with the ROI Manager under it, so neither
// covers the other
function showHelp(name, image) {
	lines = newArray("Image: " + name, "",
		"Cyan: the outlines already there. Green: the outlines you add now.",
		"Yellow: the outline selected (a circle you've drawn, until you press T).", "",
		"Remove an outline: click its number, then Delete in the ROI Manager.",
		"Add a bead: drag a circle on its dark edge with the oval tool, press T.",
		"One bead per T: an outline on a bead that already has one, or with",
		"more than one region, isn't added.",
		"Zoom with + and -. The C slider under the image switches channel.", "",
		"Each change is saved as you make it. When you're done, close the image.",
		"If outlines you add stop turning green, the macro has stopped (Esc can",
		"stop it). What you did is saved: close the image and run it again.");
	Table.create(HELP);
	Table.setColumn(HELP, lines);
	Table.showRowNumbers(false);
	Table.update;
	selectImage(image);
	getLocationAndSize(x, y, w, h);
	x = minOf(x + w, screenWidth - 600);
	height = 24 * lines.length + 70;
	Table.setLocationAndSize(x, y, 600, height, HELP);
	selectWindow("ROI Manager");
	setLocation(x, y + height);
	selectImage(image);
}

function openImage(path) {
	lower = toLowerCase(path);
	if (endsWith(lower, ".tif") || endsWith(lower, ".tiff")) {
		open(path);
	} else {
		run("Bio-Formats Importer", "open=[" + path + "] color_mode=Grayscale view=Hyperstack stack_order=XYCZT");
	}
}

function stripSlash(path) {
	while (endsWith(path, "/") || endsWith(path, "\\")) path = substring(path, 0, lengthOf(path) - 1);
	return path;
}
