import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { apca, contrast } from "../../assets/tokenResolution.js";
import { describe, maxChroma, toHex, toOklch } from "./oklch.js";

const skillDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// One seed for both modes, or a light seed and a dark seed.
type Slot = "seed" | "light" | "dark";

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
const flag = (slot: Slot) => (slot === "seed" ? "--seed" : `--${slot}-seed`);

// Light and dark seed flags make two seeds. Otherwise there is one seed.
const twoSeeds = ["light", "dark"].some((slot) => args.some((name) => name.startsWith(`--${slot}-seed`)));
const slots: Slot[] = twoSeeds ? ["light", "dark"] : ["seed"];

if (twoSeeds && args.some((name) => name.startsWith("--seed"))) {
  throw new Error("Give --seed flags or light and dark seed flags, not both");
}

// The user's color, given as a seed, sets the hue and the chroma the seeds share.
const givenSeeds = Object.fromEntries(slots.map((slot) => [slot, readHex(flag(slot))])) as Partial<Record<Slot, string>>;
const givenSeed = Object.values(givenSeeds).find((seed) => seed !== undefined);

if (Object.values(givenSeeds).filter((seed) => seed !== undefined).length > 1) {
  throw new Error("Give --light-seed or --dark-seed, not both");
}

const hue = givenSeed ? toOklch(givenSeed)[2] : readNumber("--hue", 0, 360);
const relative = givenSeed ? null : readNumber("--relative-chroma", 0, 1);
const lightnesses = Object.fromEntries(
  slots.map((slot) => {
    const given = givenSeeds[slot];

    return [slot, given ? toOklch(given)[0] : readNumber(`${flag(slot)}-lightness`, 0, 1)];
  }),
) as Record<Slot, number>;

// Two seeds are also checked against their mode's background.
const backgrounds: Partial<Record<Slot, string>> = { light: readHex("--light-background"), dark: readHex("--dark-background") };

if (Boolean(backgrounds.light) !== Boolean(backgrounds.dark)) {
  throw new Error("Give both --light-background and --dark-background, or neither");
}

if (!twoSeeds && backgrounds.light) {
  throw new Error("--light-background and --dark-background apply to two seeds");
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

// The chroma the seeds share at these seed lightnesses.
function sharedChroma(seedLightnesses: Record<Slot, number>): number {
  if (relative === null) {
    return toOklch(givenSeed as string)[1];
  }

  if (!twoSeeds) {
    return relative * maxChroma(seedLightnesses.seed, hue);
  }

  const fromLight = relative * maxChroma(seedLightnesses.light, hue);
  const fromDark = relative * maxChroma(seedLightnesses.dark, hue);

  return fromLight + (fromDark - fromLight) * darkSeedWeight();
}

// A seed at this lightness, with the shared chroma or the most sRGB holds there, whichever is less.
function seedAt(slot: Slot, lightness: number): string {
  const chroma = sharedChroma({ ...lightnesses, [slot]: lightness });

  return toHex(lightness, Math.min(chroma, maxChroma(lightness, hue)), hue);
}

const seeds = Object.fromEntries(
  slots.map((slot) => [slot, givenSeeds[slot] ?? seedAt(slot, lightnesses[slot])]),
) as Record<Slot, string>;

//==================================================
// Checks
//==================================================

// Text on a seed is white, or dark text a little lighter than the light neutral ramp's step 12.
const textColors = { white: "#FFFFFF", dark: toHex(0.26, 0, 0) };

const round = (value: number, digits = 2) => Number(value.toFixed(digits));

const meets = (element: string, ratio: number, lc: number) => {
  const { wcag, apca: lcMinimum } = thresholds[element];

  return (wcag === null || ratio >= wcag) && lc >= lcMinimum;
};

// A seed passes when white or dark text meets the seed-text minimums on it. With a background, the
// seed as text also meets the other-text minimums on that background.
function measure(seed: string, background: string | undefined) {
  const backgroundContrast = background ? { wcag: contrast(seed, background), apca: apca(seed, background) } : null;
  const text = Object.entries(textColors)
    .map(([name, hex]) => ({ name, wcag: contrast(hex, seed), apca: apca(hex, seed) }))
    .filter((candidate) => meets("seed-text", candidate.wcag, candidate.apca))
    .sort((a, b) => b.apca - a.apca)[0];
  const backgroundPasses = backgroundContrast === null || meets("other-text", backgroundContrast.wcag, backgroundContrast.apca);

  return { passes: backgroundPasses && text !== undefined, backgroundContrast, text };
}

// The closest lightness to the seed's that passes, with any other seed's lightness unchanged.
function suggest(slot: Slot): number | null {
  for (let offset = 0; offset < 1; offset += 0.005) {
    for (const candidate of [lightnesses[slot] - offset, lightnesses[slot] + offset].map((value) => round(value, 3))) {
      if (candidate > 0 && candidate < 1 && measure(seedAt(slot, candidate), backgrounds[slot]).passes) {
        return candidate;
      }
    }
  }

  return null;
}

function report(slot: Slot) {
  const seed = seeds[slot];
  const { passes, backgroundContrast, text } = measure(seed, backgrounds[slot]);
  const suggestion = passes ? null : suggest(slot);

  return {
    ...describe(seed),
    passes,
    ...(backgroundContrast
      ? { background_contrast: { wcag: round(backgroundContrast.wcag), apca: round(backgroundContrast.apca) } }
      : {}),
    text: text?.name ?? null,
    text_contrast: text ? { wcag: round(text.wcag), apca: round(text.apca) } : null,
    ...(passes ? {} : { suggestion: suggestion === null ? null : describe(seedAt(slot, suggestion)) }),
  };
}

process.stdout.write(
  `${JSON.stringify(
    twoSeeds
      ? { hue: round(hue), light_seed: report("light"), dark_seed: report("dark") }
      : { hue: round(hue), seed: report("seed") },
    null,
    2,
  )}\n`,
);
