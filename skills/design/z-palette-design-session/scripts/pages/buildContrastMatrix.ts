import { writeFile } from "node:fs/promises";
import path from "node:path";
import { apca, contrast } from "../../assets/tokenResolution.js";
import { loadPalettes } from "./loadPalettes.js";

//==================================================
// Inputs
//==================================================

const args = process.argv.slice(2);
const argument = (name: string) => {
  const index = args.indexOf(name);

  return index === -1 ? undefined : args[index + 1];
};
const palettesPath = argument("--palettes");
const paletteName = argument("--palette");
const generator = argument("--generator");
const outputPath = argument("--output");

if (!palettesPath || !paletteName || !generator || !outputPath) {
  throw new Error("--palettes, --palette, --generator, and --output are required");
}

const palette = (await loadPalettes(palettesPath)).find(
  (entry) => entry.name === paletteName && entry.generator.toLowerCase() === generator.toLowerCase(),
);

if (!palette) {
  throw new Error(`The palette file has no ${paletteName} palette from ${generator}`);
}

//==================================================
// Colors
//==================================================

type Mode = "light" | "dark";
type Color = { label: string; hex: string };

const modes: Mode[] = ["light", "dark"];
const titleCase = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);

// Every step of a ramp, light mode first.
const rampColors = (name: string, ramps: Record<Mode, string[]>): Color[] =>
  modes.flatMap((mode) =>
    ramps[mode].map((hex, index) => ({ label: `${titleCase(mode)} ${name} ${index + 1}`, hex })),
  );

// One seed shared by both modes shows once.
const seeds: Color[] =
  palette.seed.light === palette.seed.dark
    ? [{ label: "Brand", hex: palette.seed.light }]
    : modes.map((mode) => ({ label: `Brand (${titleCase(mode)})`, hex: palette.seed[mode] }));

const colors: Color[] = [
  ...seeds,
  { label: "White", hex: "#FFFFFF" },
  { label: "Black", hex: "#000000" },
  ...modes.map((mode) => ({ label: `${titleCase(mode)} Background`, hex: palette.backgrounds[mode].color })),
  ...rampColors("Brand", { light: palette.ramps.lightBrand, dark: palette.ramps.darkBrand }),
  ...rampColors("Neutral", { light: palette.ramps.lightNeutral, dark: palette.ramps.darkNeutral }),
  ...palette.signals.flatMap((signal) => rampColors(titleCase(signal.key), signal.ramps)),
];

//==================================================
// Tables
//==================================================

// Rounded down, so no value shows more contrast than the pair has.
const roundDown = (value: number, digits: number) =>
  (Math.floor(value * 10 ** digits) / 10 ** digits).toFixed(digits);

const label = (color: Color) => `${color.label} ${color.hex}`;

// Each row is the text color and each column its background.
const matrix = (measure: (text: string, background: string) => string) =>
  [
    `| Text ↓ / Background → | ${colors.map(label).join(" | ")} |`,
    `| :-- | ${colors.map(() => "--:").join(" | ")} |`,
    ...colors.map(
      (text) => `| ${label(text)} | ${colors.map((background) => measure(text.hex, background.hex)).join(" | ")} |`,
    ),
  ].join("\n");

const markdown = `# ${palette.name} (${palette.generator}) Contrast

- Rows are text colors and columns are backgrounds.
- Values are rounded down.

## WCAG 2

${matrix((text, background) => roundDown(contrast(text, background), 2))}

## APCA

${matrix((text, background) => roundDown(apca(text, background), 0))}
`;

await writeFile(outputPath, markdown, "utf8");
process.stdout.write(`${path.resolve(outputPath)}\n`);
