// edit_beads.ijm
// Fiji macro: correct the bead outlines from bead_segmentation.ijm by hand.
//
// HOW TO USE
//   1. Run bead_segmentation.ijm as usual and look through its QC images (results/qc).
//   2. Run this macro. It asks for the image folder and that run's results folder, then which
//      image to correct, and opens it with its bead outlines in the ROI Manager. Remove wrong
//      outlines, draw missed beads, click OK. It saves the outlines in a "manual_beads" folder
//      inside the image folder, then offers the next image.
//   3. Run bead_segmentation.ijm again. For each image with saved outlines it measures those
//      instead of finding its own. Then run analyze.py and make_figures.py as usual.
// Running this macro again on an image starts from its saved outlines. To go back to the
// automatic outlines, delete the image's file from manual_beads.

inputDir = stripSlash(getDirectory("Choose the folder with your images"));
outputDir = stripSlash(getDirectory("Choose the results folder of a bead_segmentation.ijm run"));
sep = File.separator;
manualDir = inputDir + sep + "manual_beads";
if (!File.exists(outputDir + sep + "settings_used.txt"))
	exit("No settings_used.txt in " + outputDir + ".\nChoose the results folder of a bead_segmentation.ijm run.");
List.setList(File.openAsString(outputDir + sep + "settings_used.txt"));
fileExt = List.get("fileExt");
segChannel = parseInt(List.get("segChannel"));

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
	for (c = 1; c <= nC; c++) {
		if (nC > 1) Stack.setChannel(c);
		run("Enhance Contrast", "saturated=0.35");
	}
	if (nC > 1) Stack.setChannel(minOf(segChannel, nC));          // start on transmitted light
	roiManager("reset");
	if (File.exists(manualZip)) roiManager("open", manualZip);   // corrected before: continue from there
	else if (File.exists(autoZip)) roiManager("open", autoZip);
	roiManager("Show All with labels");
	setTool("oval");
	waitForUser("Correct bead outlines: " + name,
		"Remove a wrong outline: click its number on the image, then click Delete in the ROI Manager.\n"
		+ "Add a missed bead: drag a circle around it with the oval tool (hold Shift for a perfect\n"
		+ "circle), then press T. Draw it on the bead's dark edge, like the other outlines (about\n"
		+ "4 um across), not around the bright halo outside it.\n \n"
		+ "Zoom in and out with + and - (mouse over the bead). The C slider under the image\n"
		+ "switches between transmitted light and fluorescence.\n \n"
		+ "Click OK when done.");

	n = roiManager("count");
	if (n == 0) {
		msg = "No outlines left, so nothing was saved for " + name
			+ ".\nTo leave this image out, add it to EXCLUDE in settings.py.";
	} else {
		roiManager("deselect");
		roiManager("Remove Channel Info");                       // outlines apply to every channel,
		roiManager("Remove Slice Info");                         // slice and frame
		roiManager("Remove Frame Info");
		File.makeDirectory(manualDir);
		roiManager("save", manualZip);
		msg = "Saved " + n + " bead outlines for " + name + ".";
	}
	if (isOpen(image)) {
		selectImage(image);
		close();
	}
	roiManager("reset");
	more = getBoolean(msg + "\n \nCorrect another image?");
}
print("Run bead_segmentation.ijm again to measure the corrected outlines.");


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
