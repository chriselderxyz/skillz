import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { apca, contrast, seedText } from "../../assets/tokenResolution.js";
import { describe, maxChroma, toHex, toOklch } from "./oklch.js";

const skillDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

type Mode = "light" | "dark";

//==================================================
// Inputs
//==================================================

const args = process.argv.slice(2);
const argument = (name: string) => {
  const index = args.indexOf(name);

  return index === -1 ? undefined : args[index + 1];
};
const readHex = (name: string) => {
  const value = argument(name);

  if (value === undefined) {
    return undefined;
  }

  if (!/^#[\da-f]{6}$/i.test(value)) {
    throw new Error(`${name} must be a six-digit HEX color`);
  }

  return value.toUpperCase();
};
const readNumber = (name: string, low: number, high: number) => {
  const value = Number(argument(name));

  if (!Number.isFinite(value) || value < low || value > high) {
    throw new Error(`${name} must be from ${low} to ${high}`);
  }

  return value;
};

// The user's color, given as one mode's seed, sets the hue and the chroma both seeds share.
const givenSeeds = { light: readHex("--light-seed"), dark: readHex("--dark-seed") };
const givenSeed = givenSeeds.light ?? givenSeeds.dark;

if (givenSeeds.light && givenSeeds.dark) {
  throw new Error("Give --light-seed or --dark-seed, not both");
}

const hue = givenSeed ? toOklch(givenSeed)[2] : readNumber("--hue", 0, 360);
const relative = givenSeed ? null : readNumber("--relative-chroma", 0, 1);
const modes: Mode[] = ["light", "dark"];
const lightnesses = Object.fromEntries(
  modes.map((mode) => {
    const given = givenSeeds[mode];

    return [mode, given ? toOklch(given)[0] : readNumber(`--${mode}-seed-lightness`, 0, 1)];
  }),
) as Record<Mode, number>;
const backgrounds = { light: readHex("--light-background"), dark: readHex("--dark-background") };

if (Boolean(backgrounds.light) !== Boolean(backgrounds.dark)) {
  throw new Error("Give both --light-background and --dark-background, or neither");
}

const thresholds = JSON.parse(await readFile(path.join(skillDirectory, "assets/contrast-thresholds.json"), "utf8"));

//==================================================
// Seeds
//==================================================

// How much of the shared chroma --relative-chroma sets from the dark seed: all of it from 70° to Radix
// lime at 126°, fading to none at 140°. Every other hue sets it from the light seed.
function darkSeedWeight(): number {
  if (hue >= 70 && hue <= 126) {
    return 1;
  }

  return hue > 126 && hue < 140 ? (140 - hue) / 14 : 0;
}

// The chroma both seeds share at these seed lightnesses.
function sharedChroma(seedLightnesses: Record<Mode, number>): number {
  if (relative === null) {
    return toOklch(givenSeed as string)[1];
  }

  const fromLight = relative * maxChroma(seedLightnesses.light, hue);
  const fromDark = relative * maxChroma(seedLightnesses.dark, hue);

  return fromLight + (fromDark - fromLight) * darkSeedWeight();
}

// A mode's seed at this lightness, with the shared chroma or the most sRGB holds there, whichever is less.
function seedAt(mode: Mode, lightness: number): string {
  const chroma = sharedChroma({ ...lightnesses, [mode]: lightness });

  return toHex(lightness, Math.min(chroma, maxChroma(lightness, hue)), hue);
}

const seeds = Object.fromEntries(
  modes.map((mode) => [mode, givenSeeds[mode] ?? seedAt(mode, lightnesses[mode])]),
) as Record<Mode, string>;

//==================================================
// Checks
//==================================================

const round = (value: number, digits = 2) => Number(value.toFixed(digits));

const meets = (element: string, ratio: number, lc: number) => {
  const { wcag, apca: lcMinimum } = thresholds[element];

  return (wcag === null || ratio >= wcag) && lc >= lcMinimum;
};

// A seed passes when it meets the non-text minimums against its mode's background, and its text,
// white or black from seedText, meets the seed-text minimums on it.
function measure(seed: string, background: string) {
  const backgroundContrast = { wcag: contrast(seed, background), apca: apca(seed, background) };
  const hex = seedText(seed);
  const text = { name: hex === "#FFFFFF" ? "white" : "black", wcag: contrast(hex, seed), apca: apca(hex, seed) };

  return {
    passes:
      meets("non-text", backgroundContrast.wcag, backgroundContrast.apca) && meets("seed-text", text.wcag, text.apca),
    backgroundContrast,
    text,
  };
}

// The closest lightness to the seed's that passes, with the other seed's lightness unchanged.
function suggest(mode: Mode, background: string): number | null {
  for (let offset = 0; offset < 1; offset += 0.005) {
    for (const candidate of [lightnesses[mode] - offset, lightnesses[mode] + offset].map((value) => round(value, 3))) {
      if (candidate > 0 && candidate < 1 && measure(seedAt(mode, candidate), background).passes) {
        return candidate;
      }
    }
  }

  return null;
}

// Without backgrounds, a seed is reported unchecked.
function report(mode: Mode) {
  const seed = seeds[mode];
  const background = backgrounds[mode];

  if (background === undefined) {
    return describe(seed);
  }

  const { passes, backgroundContrast, text } = measure(seed, background);
  const suggestion = passes ? null : suggest(mode, background);

  return {
    ...describe(seed),
    passes,
    background_contrast: { wcag: round(backgroundContrast.wcag), apca: round(backgroundContrast.apca) },
    text: text.name,
    text_contrast: { wcag: round(text.wcag), apca: round(text.apca) },
    ...(passes ? {} : { suggestion: suggestion === null ? null : describe(seedAt(mode, suggestion)) }),
  };
}

process.stdout.write(
  `${JSON.stringify({ hue: round(hue), light_seed: report("light"), dark_seed: report("dark") }, null, 2)}\n`,
);
