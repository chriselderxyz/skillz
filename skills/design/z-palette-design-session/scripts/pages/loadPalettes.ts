import { readFile } from "node:fs/promises";
import path from "node:path";
import { toOklch } from "../colors/oklch.js";

type Mode = "light" | "dark";
type SignalKey = "destructive" | "warning" | "success";

type PaletteFileEntry = {
  name: string;
  generator: string;
  description: string;
  suggested_brand: Mode;
  brand: string;
} & Record<SignalKey, string>;

type GeneratorRamp = {
  base_ramp: { color: string }[];
  alpha_ramp: string[];
  wide_gamut_ramp?: string[];
  wide_gamut_alpha_ramp?: string[];
};

type GeneratorOutput = {
  name: string;
  inputs: { light_seed: string; dark_seed: string; light_gray: string; dark_gray: string };
} & Record<Mode, { background: string; brand: GeneratorRamp; neutral: GeneratorRamp }>;

const signalKeys: SignalKey[] = ["destructive", "warning", "success"];
const modes: Mode[] = ["light", "dark"];

//==================================================
// Colors
//==================================================

const steps = (ramp: GeneratorRamp) => ramp.base_ramp.map((step) => step.color.toUpperCase());
const alphaSteps = (ramp: GeneratorRamp) => ramp.alpha_ramp.map((value) => value.toUpperCase());

function backgroundsOf(output: GeneratorOutput) {
  return Object.fromEntries(
    modes.map((mode) => {
      const color = output[mode].background.toUpperCase();

      return [mode, { color, lightness: Number((toOklch(color)[0] * 100).toFixed(1)) }];
    }),
  ) as Record<Mode, { color: string; lightness: number }>;
}

// Wide gamut ramps by mode and ramp, when the generator produced them.
function wideGamut(output: GeneratorOutput, ramps: Record<string, [Mode, "brand" | "neutral"]>) {
  const [firstMode, firstRamp] = Object.values(ramps)[0];

  if (!output[firstMode][firstRamp].wide_gamut_ramp) {
    return {};
  }

  const pick = (key: "wide_gamut_ramp" | "wide_gamut_alpha_ramp") =>
    Object.fromEntries(Object.entries(ramps).map(([name, [mode, ramp]]) => [name, output[mode][ramp][key]]));

  return { wideGamutRamps: pick("wide_gamut_ramp"), wideGamutAlphaRamps: pick("wide_gamut_alpha_ramp") };
}

//==================================================
// Palettes
//==================================================

// The ramp's color name: the output name without its trailing HEX values.
function rampName(output: GeneratorOutput): string {
  const parts = output.name.split("-");

  while (parts.length > 1 && /^[\da-f]{6}$/.test(parts[parts.length - 1])) {
    parts.pop();
  }

  const name = parts.join(" ");

  return name.charAt(0).toUpperCase() + name.slice(1);
}

// The seed for each mode.
function seedsOf(output: GeneratorOutput): Record<Mode, string> {
  return {
    light: output.inputs.light_seed.toUpperCase(),
    dark: output.inputs.dark_seed.toUpperCase(),
  };
}

async function readOutput(palettesPath: string, outputPath: string): Promise<GeneratorOutput> {
  return JSON.parse(await readFile(path.resolve(path.dirname(palettesPath), outputPath), "utf8"));
}

// Reads the palette file and each generator output it lists. Returns one palette object per entry.
export async function loadPalettes(palettesPath: string) {
  const file: { palettes: PaletteFileEntry[] } = JSON.parse(await readFile(palettesPath, "utf8"));

  return Promise.all(
    file.palettes.map(async (entry) => {
      const brand = await readOutput(palettesPath, entry.brand);
      const generator = entry.generator.charAt(0).toUpperCase() + entry.generator.slice(1);
      const signals = await Promise.all(
        signalKeys.map(async (key) => {
          const output = await readOutput(palettesPath, entry[key]);

          return {
            key,
            name: rampName(output),
            seed: seedsOf(output),
            generator,
            backgrounds: backgroundsOf(output),
            ramps: { light: steps(output.light.brand), dark: steps(output.dark.brand) },
            alphaRamps: { light: alphaSteps(output.light.brand), dark: alphaSteps(output.dark.brand) },
            ...wideGamut(output, { light: ["light", "brand"], dark: ["dark", "brand"] }),
          };
        }),
      );

      return {
        name: entry.name,
        generator,
        description: entry.description,
        seed: seedsOf(brand),
        suggestedBrand: entry.suggested_brand,
        gray: { light: brand.inputs.light_gray.toUpperCase(), dark: brand.inputs.dark_gray.toUpperCase() },
        grayChroma: {
          light: Number(toOklch(brand.inputs.light_gray)[1].toFixed(3)),
          dark: Number(toOklch(brand.inputs.dark_gray)[1].toFixed(3)),
        },
        backgrounds: backgroundsOf(brand),
        ramps: {
          lightBrand: steps(brand.light.brand),
          lightNeutral: steps(brand.light.neutral),
          darkBrand: steps(brand.dark.brand),
          darkNeutral: steps(brand.dark.neutral),
        },
        alphaRamps: {
          lightBrand: alphaSteps(brand.light.brand),
          lightNeutral: alphaSteps(brand.light.neutral),
          darkBrand: alphaSteps(brand.dark.brand),
          darkNeutral: alphaSteps(brand.dark.neutral),
        },
        ...wideGamut(brand, {
          lightBrand: ["light", "brand"],
          lightNeutral: ["light", "neutral"],
          darkBrand: ["dark", "brand"],
          darkNeutral: ["dark", "neutral"],
        }),
        signals,
      };
    }),
  );
}
