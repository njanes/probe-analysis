// edit_beads.ijm
// Fiji macro: correct the bead outlines from bead_segmentation.ijm by hand.
//
// HOW TO USE
//   1. Run bead_segmentation.ijm as usual and look through its QC images (results/qc).
//   2. Run this macro. It asks for the experiment folder (with the images) and its results folder,
//      then which image to start with, and opens it with its bead outlines in cyan. Remove wrong
//      outlines, and add missed beads one at a time with the oval tool and T: each one added
//      turns green. Then press N (or the green arrow on the toolbar) to save this image's
//      outlines and go on to the next image, or X (the red cross) to discard this image's changes.
//      The outlines are saved in a "manual_beads" folder inside the experiment folder. Closing
//      the image saves it too, and stops. The hotkeys can be changed in the first window.
//   3. Run bead_segmentation.ijm again, choosing the same results folder, and click Update: it
//      measures again only the images whose outlines you corrected since, using your outlines
//      instead of finding its own. Then run analyze.py and make_figures.py as usual.
// Running this macro again on an image starts from its saved outlines (all cyan then). To go
// back to the automatic outlines, delete the image's file from manual_beads.
//
// The hotkeys and toolbar buttons are a small macro set installed while this macro runs: each one
// only passes its action to the loop below. Fiji's own startup macros are put back at the end.

var FOUND = "cyan";     // outlines already there when the image opens (found by the macro, or saved before)
var ADDED = "green";    // outlines added while the image is open
var HELP = "How to correct the outlines";
var ACTION = "edit_beads.action";   // set by a hotkey or button, read by the loop below
var ALIVE = "edit_beads.alive";     // the loop's last time round: the hotkeys work only while it runs
var ACTIONS = newArray("next", "discard", "showall", "labels", "delete");
var NAMES = newArray("Next image (saves this one)", "Discard the changes to this image",
	"Show or hide all the outlines", "Show or hide their numbers", "Delete the selected outline");
var DEFAULT_KEYS = newArray("n", "x", "a", "l", "d");
// puts Fiji's (or ImageJ's) own startup macros, with their hotkeys and tools, back in place
var RESTORE = "d = getDirectory('macros'); done = false;"
	+ " names = newArray('StartupMacros.fiji.ijm', 'StartupMacros.txt', 'StartupMacros.ijm');"
	+ " for (i = 0; i < names.length; i++) if (!done && File.exists(d + names[i])) {"
	+ " run('Install...', 'install=[' + d + names[i] + ']'); done = true; }"
	+ " if (!done) r = call('ij.plugin.MacroInstaller.installFromJar', '/macros/StartupMacros.txt');";

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

keys = newArray(ACTIONS.length);
for (i = 0; i < ACTIONS.length; i++) keys[i] = call("ij.Prefs.get", "edit_beads." + ACTIONS[i], DEFAULT_KEYS[i]);
Dialog.create("Correct bead outlines");
Dialog.addChoice("Start with image", images, images[0]);
Dialog.addMessage("Hotkeys:\n" + keyList(keys, "\n"));
Dialog.addCheckbox("Change the hotkeys", false);
Dialog.show();
first = Dialog.getChoice();
start = 0;
for (k = 0; k < images.length; k++) if (images[k] == first) start = k;
if (Dialog.getCheckbox()) askKeys(keys);
installControls(keys);

saved = 0;
stopped = false;
for (k = start; k < images.length && !stopped; k++) {
	name = images[k];
	base = substring(name, 0, lastIndexOf(name, "."));
	manualZip = manualDir + sep + base + "_RoiSet.zip";
	autoZip = outputDir + sep + "rois" + sep + base + "_RoiSet.zip";

	r = call("java.lang.System.setProperty", ALIVE, d2s(getTime(), 0));
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
	loadOutlines(manualZip, autoZip);
	showAll = true;
	labels = true;
	showOutlines(showAll, labels);
	setTool("oval");
	showHelp(name, k, images.length, image, keys);

	// Until N, or the image is closed: check each outline added with T as it arrives and colour it,
	// and carry out each hotkey or button pressed
	r = call("java.lang.System.setProperty", ACTION, "none");  // drop any press made while the image opened
	changed = false;
	result = "";
	n = roiManager("count");
	while (result == "") {
		wait(100);
		r = call("java.lang.System.setProperty", ALIVE, d2s(getTime(), 0));
		if (!isOpen(image)) {
			result = "closed";
		} else {
			c = roiManager("count");
			if (c > n) {
				selectImage(image);
				for (j = c - 1; j >= n; j--) if (check(j, um, minDiam, maxDiam)) changed = true;
				run("Select None");
			} else if (c < n) changed = true;                     // removed with Delete in the ROI Manager
			a = call("java.lang.System.getProperty", ACTION);
			if (a != "none") {
				r = call("java.lang.System.setProperty", ACTION, "none");
				selectImage(image);
				if (a == "next") result = "next";
				if (a == "discard") {
					loadOutlines(manualZip, autoZip);
					showOutlines(showAll, labels);
					changed = false;
				}
				if (a == "showall") {
					showAll = !showAll;
					showOutlines(showAll, labels);
				}
				if (a == "labels") {
					labels = !labels;
					showAll = true;
					showOutlines(showAll, labels);
				}
				if (a == "delete") {
					i = roiManager("index");
					if (i >= 0) {
						roiManager("select", i);
						roiManager("delete");
						changed = true;
					}
					run("Select None");
				}
			}
			n = roiManager("count");
		}
	}

	if (changed) {
		if (roiManager("count") == 0) {
			showMessage("Nothing saved", "No outlines left, so nothing was saved for " + name
				+ ".\nTo leave this image out, add it to EXCLUDE in settings.py.");
		} else {
			saveOutlines(manualDir, manualZip);
			saved++;
		}
	}
	roiManager("reset");
	if (result == "closed") stopped = true;
	else {                                                      // "next": on to the next image
		selectImage(image);
		close();
	}
}

r = call("java.lang.System.setProperty", ALIVE, "0");
eval(RESTORE);
if (isOpen(HELP)) {
	selectWindow(HELP);
	run("Close");
}
msg = "Saved corrected outlines for " + saved + " image(s).";
if (!stopped) msg = "That was the last image. " + msg;
showMessage("Correct bead outlines", msg + "\n \nTo measure them, run bead_segmentation.ijm again into the same "
	+ "results folder and click Update.");


// An outline just added (number k) is kept, in the added colour, if it is one region the size of a
// bead on a bead without an outline; otherwise it is removed again, with a message saying why.
// Returns whether it was kept.
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
		return false;
	}
	roiManager("Remove Channel Info");                           // shown on every channel
	roiManager("Remove Slice Info");
	roiManager("Remove Frame Info");
	roiManager("Set Color", ADDED);
	return true;
}

// The image's outlines as saved: corrected before (manual_beads), else as found by bead_segmentation.ijm
function loadOutlines(manualZip, autoZip) {
	roiManager("reset");
	if (File.exists(manualZip)) roiManager("open", manualZip);
	else if (File.exists(autoZip)) roiManager("open", autoZip);
	for (i = 0; i < roiManager("count"); i++) {
		roiManager("select", i);
		roiManager("Set Color", FOUND);
	}
	run("Select None");
}

function showOutlines(showAll, labels) {
	if (!showAll) roiManager("Show None");
	else if (labels) roiManager("Show All with labels");
	else roiManager("Show All without labels");
}

function saveOutlines(manualDir, manualZip) {
	roiManager("deselect");
	roiManager("Remove Channel Info");                           // outlines apply to every channel,
	roiManager("Remove Slice Info");                             // slice and frame
	roiManager("Remove Frame Info");
	File.makeDirectory(manualDir);
	roiManager("save", manualZip);
}

// Asks for new hotkeys until they are usable, then keeps them for next time (in Fiji's preferences)
function askKeys(keys) {
	why = "first";
	while (why != "") {
		Dialog.create("Hotkeys");
		Dialog.addMessage("Each one a letter or a digit (a capital letter means with Shift), or F1 to F12.\n"
			+ "T can't be one: it adds an outline.");
		for (i = 0; i < keys.length; i++) Dialog.addString(NAMES[i], keys[i], 4);
		Dialog.show();
		for (i = 0; i < keys.length; i++) {
			keys[i] = Dialog.getString();
			if (matches(keys[i], "[fF][0-9]+")) keys[i] = toUpperCase(keys[i]);
		}
		why = "";
		for (i = 0; i < keys.length; i++) {
			if (!matches(keys[i], "[a-zA-Z0-9]|F[1-9]|F1[0-2]"))
				why = NAMES[i] + ": \"" + keys[i] + "\" isn't a letter, a digit or F1 to F12.";
			else if (keys[i] == "t") why = "T adds an outline, so it can't be a hotkey.";
			for (j = 0; j < i; j++) if (keys[j] == keys[i]) why = "\"" + keys[i] + "\" is used twice.";
		}
		if (why != "") showMessage("Hotkeys", why);
	}
	for (i = 0; i < keys.length; i++) r = call("ij.Prefs.set", "edit_beads." + ACTIONS[i], keys[i]);
	r = call("ij.Prefs.savePreferences");
}

function keyList(keys, glue) {
	s = "";
	for (i = 0; i < keys.length; i++) {
		if (i > 0) s = s + glue;
		s = s + "    " + keys[i] + "    " + NAMES[i];
	}
	return s;
}

// Installs the hotkeys, and a Next and a Discard button on the toolbar. Each passes its action to the
// loop in the main macro; if that has stopped, it puts Fiji's own startup macros back instead.
function installControls(keys) {
	text = "";
	for (i = 0; i < keys.length; i++)
		text = text + "macro \"" + NAMES[i] + " [" + keys[i] + "]\" { act(\"" + ACTIONS[i] + "\"); }\n";
	text = text + "macro \"" + NAMES[0] + " Action Tool - C080H42d84e00\" { act(\"next\"); }\n"
		+ "macro \"" + NAMES[1] + " Action Tool - Cc00L33ccL3cc3L43dcL4cd3L34cdL3dc4\" { act(\"discard\"); }\n"
		+ "function act(a) {\n"
		+ "  alive = parseFloat(\"\" + call(\"java.lang.System.getProperty\", \"" + ALIVE + "\"));\n"
		+ "  if (isNaN(alive) || getTime() - alive > 30000) {\n"
		+ "    " + RESTORE + "\n"
		+ "    showMessage(\"edit_beads.ijm isn't running\", \"edit_beads.ijm has stopped, so its hotkeys and buttons\\n"
		+ "are off now. Run it again to carry on (changes since the last Next weren't saved).\");\n"
		+ "    return;\n"
		+ "  }\n"
		+ "  r = call(\"java.lang.System.setProperty\", \"" + ACTION + "\", a);\n"
		+ "}\n";
	path = getDirectory("temp") + "edit_beads_controls.ijm";
	File.saveString(text, path);
	run("Install...", "install=[" + path + "]");
}

// The instructions, in a window to the right of the image with the ROI Manager under it, so neither
// covers the other
function showHelp(name, k, total, image, keys) {
	lines = newArray("Image " + (k + 1) + " of " + total + ": " + name, "",
		"Cyan: the outlines already there. Green: the outlines you add now.",
		"Yellow: the outline selected (a circle you've drawn, until you press T).", "",
		"Add a bead: drag a circle on its dark edge with the oval tool, press T.",
		"One bead per T: an outline on a bead that already has one, or with",
		"more than one region, isn't added.",
		"Remove an outline: click its number, then press " + keys[4] + ".", "",
		"Hotkeys (toolbar: green arrow = next, red cross = discard):");
	for (i = 0; i < keys.length; i++) lines = Array.concat(lines, "    " + keys[i] + "    " + NAMES[i]);
	lines = Array.concat(lines, "", "Zoom with + and -. The C slider under the image switches channel.",
		"Closing the image saves its changes too, and stops.");
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
