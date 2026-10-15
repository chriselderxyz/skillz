import path from "node:path";
import { pathToFileURL } from "node:url";
import Color from "colorjs.io";

//==================================================
// Neutral Tint
//==================================================

// Muted mid gray in the seed's hue. This is the neutral ramp's tint.

export function makeGray(seed: string): string {
	if (!/^#[\da-f]{6}$/i.test(seed)) {
		throw new Error("seed must be a six-digit HEX color");
	}

	const color = new Color(seed).to("oklch");
	const hue = Number.isNaN(color.coords[2]) ? 0 : color.coords[2];
	let gray = new Color("oklch", [0.55, 0.012, hue])
		.to("srgb")
		.toString({ format: "hex" })
		.toUpperCase();

	if (gray.length === 4) {
		gray = `#${gray[1]}${gray[1]}${gray[2]}${gray[2]}${gray[3]}${gray[3]}`;
	}

	return gray;
}

//==================================================
// Command Line Entry Point
//==================================================

const isEntryPoint =
	process.argv[1] !== undefined &&
	import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;

if (isEntryPoint) {
	const args = process.argv.slice(2);
	const seedIndex = args.indexOf("--seed");
	const seed = seedIndex === -1 ? "" : args[seedIndex + 1];

	process.stdout.write(`${JSON.stringify({ gray: makeGray(seed) }, null, 2)}\n`);
}
