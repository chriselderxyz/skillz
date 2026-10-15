import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { apca, contrast } from "../../assets/tokenResolution.js";
import { describe, maxChroma, relativeChroma, seedColor, toHex, toOklch } from "./oklch.js";

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

// The user's color, given as one mode's seed, sets the hue and that seed's relative chroma.
const givenSeeds = { light: readHex("--light-seed"), dark: readHex("--dark-seed") };
const givenSeed = givenSeeds.light ?? givenSeeds.dark;

if (givenSeeds.light && givenSeeds.dark) {
  throw new Error("Give --light-seed or --dark-seed, not both");
}

const hue = givenSeed ? toOklch(givenSeed)[2] : readNumber("--hue", 0, 360);
const modes: Mode[] = ["light", "dark"];
const shares = Object.fromEntries(
  modes.map((mode) => {
    const given = givenSeeds[mode];

    return [mode, given ? relativeChroma(given) : readNumber(`--${mode}-relative-chroma`, 0, 1)];
  }),
) as Record<Mode, number>;
const lightnesses = Object.fromEntries(
  modes.map((mode) => {
    const given = givenSeeds[mode];

    return [mode, given ? toOklch(given)[0] : readNumber(`--${mode}-seed-lightness`, 0, 1)];
  }),
) as Record<Mode, number>;
const seeds = Object.fromEntries(
  modes.map((mode) => [mode, givenSeeds[mode] ?? seedColor(lightnesses[mode], shares[mode], hue)]),
) as Record<Mode, string>;
const backgrounds = { light: readHex("--light-background"), dark: readHex("--dark-background") };

if (!backgrounds.light || !backgrounds.dark) {
  throw new Error("--light-background and --dark-background are required");
}

const thresholds = JSON.parse(await readFile(path.join(skillDirectory, "assets/contrast-thresholds.json"), "utf8"));

//==================================================
// Checks
//==================================================

// Text on a seed is white, or dark text a little lighter than the light neutral ramp's step 12.
const textColors = { white: "#FFFFFF", dark: toHex(0.26, 0, 0) };

const round = (value: number, digits = 2) => Number(value.toFixed(digits));

// Radix's step 9 colors that carry dark text, the most chroma Radix gives a pale step 9 at each hue.
// A dark seed's chroma stays at or under the ceiling interpolated between them by hue. Outside their
// hue range, sRGB already holds pale colors to less chroma.
const paleStepNines = ["#FFC53D", "#FFE629", "#BDEE63", "#86EAD4", "#7CE2FE"]
  .map((hex) => {
    const [, chroma, stepHue] = toOklch(hex);

    return { hue: stepHue, chroma };
  })
  .sort((a, b) => a.hue - b.hue);

function chromaCeiling(): number | null {
  const above = paleStepNines.findIndex((step) => step.hue >= hue);

  if (above === -1 || (above === 0 && (paleStepNines[0] as { hue: number }).hue !== hue)) {
    return null;
  }

  const upper = paleStepNines[above] as { hue: number; chroma: number };
  const lower = paleStepNines[Math.max(0, above - 1)] as { hue: number; chroma: number };
  const position = upper.hue === lower.hue ? 0 : (hue - lower.hue) / (upper.hue - lower.hue);

  return lower.chroma + (upper.chroma - lower.chroma) * position;
}

const meets = (element: string, ratio: number, lc: number) => {
  const { wcag, apca: lcMinimum } = thresholds[element];

  return (wcag === null || ratio >= wcag) && lc >= lcMinimum;
};

// A seed passes when it meets the non-text minimums against its mode's background, and white or
// dark text meets the seed-text minimums on it.
function measure(seed: string, background: string) {
  const backgroundContrast = { wcag: contrast(seed, background), apca: apca(seed, background) };
  const text = Object.entries(textColors)
    .map(([name, hex]) => ({ name, wcag: contrast(hex, seed), apca: apca(hex, seed) }))
    .filter((candidate) => meets("seed-text", candidate.wcag, candidate.apca))
    .sort((a, b) => b.apca - a.apca)[0];

  return {
    passes: meets("non-text", backgroundContrast.wcag, backgroundContrast.apca) && text !== undefined,
    backgroundContrast,
    text,
  };
}

// The closest lightness to the seed's that passes, at the same hue and relative chroma.
function suggest(seed: string, background: string, share: number): number | null {
  const [lightness] = toOklch(seed);

  for (let offset = 0; offset < 1; offset += 0.005) {
    for (const candidate of [lightness - offset, lightness + offset]) {
      if (candidate > 0 && candidate < 1 && measure(seedColor(candidate, share, hue), background).passes) {
        return round(candidate, 3);
      }
    }
  }

  return null;
}

function report(mode: Mode) {
  const seed = seeds[mode];
  const { passes: contrastPasses, backgroundContrast, text } = measure(seed, backgrounds[mode] as string);
  const suggestion = contrastPasses ? null : suggest(seed, backgrounds[mode] as string, shares[mode]);
  const ceiling = mode === "dark" && !givenSeeds.dark ? chromaCeiling() : null;
  const most = maxChroma(lightnesses[mode], hue);
  const aboveCeiling = ceiling !== null && shares[mode] * most > ceiling;
  const passes = contrastPasses && !aboveCeiling;

  return {
    ...describe(seed),
    passes,
    ...(ceiling === null ? {} : { chroma_ceiling: round(ceiling, 3) }),
    ...(aboveCeiling && ceiling !== null ? { ceiling_relative_chroma: Math.floor((ceiling / most) * 1000) / 1000 } : {}),
    background_contrast: { wcag: round(backgroundContrast.wcag), apca: round(backgroundContrast.apca) },
    text: text?.name ?? null,
    text_contrast: text ? { wcag: round(text.wcag), apca: round(text.apca) } : null,
    ...(contrastPasses ? {} : { suggestion: suggestion === null ? null : describe(seedColor(suggestion, shares[mode], hue)) }),
  };
}

process.stdout.write(
  `${JSON.stringify({ hue: round(hue), light_seed: report("light"), dark_seed: report("dark") }, null, 2)}\n`,
);
