import path from "node:path";
import { pathToFileURL } from "node:url";
import Color from "colorjs.io";

//==================================================
// Neutral Tint
//==================================================

// Muted mid gray in the brand hue. This is the neutral ramp's tint.

export function deriveBackground(brandColor: string): string {
	if (!/^#[\da-f]{6}$/i.test(brandColor)) {
		throw new Error("brandColor must be a six-digit HEX color");
	}

	const brand = new Color(brandColor).to("oklch");
	const hue = Number.isNaN(brand.coords[2]) ? 0 : brand.coords[2];
	let backgroundColor = new Color("oklch", [0.55, 0.012, hue])
		.to("srgb")
		.toString({ format: "hex" })
		.toUpperCase();

	if (backgroundColor.length === 4) {
		backgroundColor = `#${backgroundColor[1]}${backgroundColor[1]}${backgroundColor[2]}${backgroundColor[2]}${backgroundColor[3]}${backgroundColor[3]}`;
	}

	return backgroundColor;
}

//==================================================
// Command Line Entry Point
//==================================================

const isEntryPoint =
	process.argv[1] !== undefined &&
	import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;

if (isEntryPoint) {
	const args = process.argv.slice(2);
	const brandColorIndex = args.indexOf("--brand-color");
	const brandColor = brandColorIndex === -1 ? "" : args[brandColorIndex + 1];
	const backgroundColor = deriveBackground(brandColor);

	process.stdout.write(`${JSON.stringify({ background_color: backgroundColor }, null, 2)}\n`);
}
