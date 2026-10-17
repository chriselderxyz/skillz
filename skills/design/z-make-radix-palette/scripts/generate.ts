import { writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import Color from "colorjs.io";
import {
  generateRadixColors,
  getAlphaColorP3,
  getAlphaColorSrgb,
  toOklchString,
} from "./generateRadixColors.js";

type GenerateOptions = {
  lightSeed: string;
  darkSeed?: string;
  brandColorName: string;
  lightGray: string;
  darkGray: string;
  lightBackground?: string;
  darkBackground?: string;
  outputDirectory?: string;
};

type StepContrast = {
  background: number;
  apca_background: number;
  brand_2: number;
  apca_brand_2: number;
  white: number;
  apca_white: number;
  black: number;
  apca_black: number;
} & Record<string, number>;

type RampStep = {
  step: number;
  role: string;
  color: string;
  contrast: StepContrast;
};

const roles = [
  "app-background",
  "subtle-background",
  "component-fill",
  "component-fill-hover",
  "component-fill-active",
  "subtle-border",
  "border",
  "strong-border",
  "solid-fill",
  "solid-fill-hover",
  "low-contrast-text",
  "high-contrast-text",
] as const;

//==================================================
// Contrast
//==================================================

// Each step.contrast value is measured against the named reference.
// Keys without an apca_ prefix are the Web Content Accessibility Guidelines 2
// contrast ratio. They are unsigned and at least 1.
// Keys with an apca_ prefix are the Accessible Perceptual Contrast Algorithm,
// the contrast method in the Web Content Accessibility Guidelines 3 draft.
// Those values are signed lightness contrast: positive means the step is darker
// than the reference, negative means it is lighter.
// brand_2 is the brand ramp's step 2.
// neutral_1 through neutral_12 are the neutral ramp steps.
function measureRamp(
  colors: readonly string[],
  background: string,
  brandStep2: string,
  neutralColors: readonly string[],
): RampStep[] {
  const backgroundColor = new Color(background);
  const brandStep2Color = new Color(brandStep2);
  const white = new Color("#FFFFFF");
  const black = new Color("#000000");
  const neutralReferences = neutralColors.map((neutralColor, neutralIndex) => {
    return {
      stepNumber: neutralIndex + 1,
      color: new Color(neutralColor),
    };
  });

  return colors.map((color, index) => {
    const foreground = new Color(color);
    const role = roles[index];

    if (role === undefined) {
      throw new Error(`Ramp step ${index + 1} has no role`);
    }

    const contrast: StepContrast = {
      background: Number(foreground.contrastWCAG21(backgroundColor).toFixed(2)),
      apca_background: Number(backgroundColor.contrastAPCA(foreground).toFixed(2)),
      brand_2: Number(foreground.contrastWCAG21(brandStep2Color).toFixed(2)),
      apca_brand_2: Number(brandStep2Color.contrastAPCA(foreground).toFixed(2)),
      white: Number(foreground.contrastWCAG21(white).toFixed(2)),
      apca_white: Number(white.contrastAPCA(foreground).toFixed(2)),
      black: Number(foreground.contrastWCAG21(black).toFixed(2)),
      apca_black: Number(black.contrastAPCA(foreground).toFixed(2)),
    };

    for (const neutralReference of neutralReferences) {
      contrast[`neutral_${neutralReference.stepNumber}`] = Number(
        foreground.contrastWCAG21(neutralReference.color).toFixed(2),
      );
      contrast[`apca_neutral_${neutralReference.stepNumber}`] = Number(
        neutralReference.color.contrastAPCA(foreground).toFixed(2),
      );
    }

    return {
      step: index + 1,
      role,
      color,
      contrast,
    };
  });
}

//==================================================
// HEX
//==================================================

function toLongHex(hex: string): string {
  if (hex.length === 4) {
    return `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
  }

  return hex;
}

function withLongHex(colors: ReturnType<typeof generateRadixColors>) {
  return {
    ...colors,
    background: toLongHex(colors.background),
    accentContrast: toLongHex(colors.accentContrast),
    accentScale: colors.accentScale.map(toLongHex),
    grayScale: colors.grayScale.map(toLongHex),
  };
}

//==================================================
// Step Minimums
//==================================================

// Step 11 meets 4.5:1 and APCA Lc 60, and step 12 meets 7:1 and Lc 75, on the background and on
// steps 1–5 of their ramp. Brand step 8 meets 3:1 and Lc 45 on the background and on steps 1–2.
// Brand steps also meet their minimums on the same neutral steps.
const stepMinimums = [
  { index: 7, wcag: 3, apca: 45, surfaceSteps: 3, brandOnly: true },
  { index: 10, wcag: 4.5, apca: 60, surfaceSteps: 5, brandOnly: false },
  { index: 11, wcag: 7, apca: 75, surfaceSteps: 5, brandOnly: false },
];

// WCAG 2 contrast ratio, from the relative luminance of each six-digit HEX color.
function contrastRatio(a: string, b: string) {
  const luminance = (hex: string) => {
    const [red, green, blue] = [1, 3, 5].map((offset) => {
      const channel = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;

      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });

    return 0.2126 * (red as number) + 0.7152 * (green as number) + 0.0722 * (blue as number);
  };
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);

  return ((high as number) + 0.05) / ((low as number) + 0.05);
}

function meetsStepMinimum(hex: string, surfaces: string[], minimum: (typeof stepMinimums)[number]) {
  const step = new Color(hex);

  return surfaces.every(
    (surface) =>
      contrastRatio(hex, surface) >= minimum.wcag &&
      Math.abs(new Color(surface).contrastAPCA(step)) >= minimum.apca,
  );
}

// Moves each step that falls short darker in light mode, or lighter in dark mode, keeping its hue
// and chroma, then rebuilds its alpha and wide gamut values.
function applyStepMinimums(colors: ReturnType<typeof withLongHex>, appearance: "light" | "dark") {
  const scales = [
    ["accentScale", "accentScaleAlpha", "accentScaleWideGamut", "accentScaleAlphaWideGamut"],
    ["grayScale", "grayScaleAlpha", "grayScaleWideGamut", "grayScaleAlphaWideGamut"],
  ] as const;
  const result = { ...colors };

  for (const [solidKey, alphaKey, wideGamutKey, wideGamutAlphaKey] of scales) {
    const solid = [...result[solidKey]];
    const alpha = [...result[alphaKey]];
    const wideGamut = [...result[wideGamutKey]];
    const wideGamutAlpha = [...result[wideGamutAlphaKey]];
    const brand = solidKey === "accentScale";

    for (const minimum of stepMinimums) {
      if (minimum.brandOnly && !brand) {
        continue;
      }

      const surfaces = [
        colors.background,
        ...solid.slice(0, minimum.surfaceSteps),
        ...(brand ? colors.grayScale.slice(0, minimum.surfaceSteps) : []),
      ] as string[];
      let hex = solid[minimum.index] as string;

      if (meetsStepMinimum(hex, surfaces, minimum)) {
        continue;
      }

      const step = new Color(hex).to("oklch");

      while (!meetsStepMinimum(hex, surfaces, minimum) && step.coords[0] > 0 && step.coords[0] < 1) {
        step.coords[0] += appearance === "light" ? -0.001 : 0.001;
        hex = toLongHex(step.to("srgb").toString({ format: "hex" }));
      }

      solid[minimum.index] = hex;
      alpha[minimum.index] = getAlphaColorSrgb(hex, colors.background);
      wideGamut[minimum.index] = toOklchString(step);
      wideGamutAlpha[minimum.index] = getAlphaColorP3(hex, colors.background);
    }

    Object.assign(result, {
      [solidKey]: solid,
      [alphaKey]: alpha,
      [wideGamutKey]: wideGamut,
      [wideGamutAlphaKey]: wideGamutAlpha,
    });
  }

  return result;
}

//==================================================
// Entry Point for Ramp Generation
//==================================================

export async function generate({
  lightSeed,
  darkSeed = lightSeed,
  brandColorName,
  lightGray,
  darkGray,
  lightBackground = "#FFFFFF",
  darkBackground = "#141414",
  outputDirectory = process.cwd(),
}: GenerateOptions): Promise<string> {
  const normalizedBrandColorName = brandColorName.toLowerCase();

  if (!/^[a-z][a-z0-9-]*$/.test(normalizedBrandColorName)) {
    throw new Error(
      "brandColorName must start with a letter and use only letters, numbers, and hyphens",
    );
  }
  const colorInputs = {
    light_seed: lightSeed,
    dark_seed: darkSeed,
    light_gray: lightGray,
    dark_gray: darkGray,
    light_background: lightBackground,
    dark_background: darkBackground,
  };

  for (const [name, value] of Object.entries(colorInputs)) {
    if (!/^#[\da-f]{6}$/i.test(value)) {
      throw new Error(`${name} must be a six-digit HEX color`);
    }
  }

  const normalizedColors = Object.fromEntries(
    Object.entries(colorInputs).map(([name, value]) => {
      const hex = toLongHex(
        new Color(value).to("srgb").toString({ format: "hex" }).toUpperCase(),
      );

      return [name, hex];
    }),
  ) as Record<keyof typeof colorInputs, string>;

  const seedNames =
    normalizedColors.dark_seed === normalizedColors.light_seed
      ? [normalizedColors.light_seed]
      : [normalizedColors.light_seed, normalizedColors.dark_seed];
  const grayNames =
    normalizedColors.dark_gray === normalizedColors.light_gray
      ? [normalizedColors.light_gray]
      : [normalizedColors.light_gray, normalizedColors.dark_gray];
  const outputName = [normalizedBrandColorName, ...seedNames, ...grayNames]
    .map((part) => part.replace("#", ""))
    .join("-")
    .toLowerCase();

  const light = applyStepMinimums(
    withLongHex(
      generateRadixColors({
        appearance: "light",
        accent: normalizedColors.light_seed,
        gray: normalizedColors.light_gray,
        background: normalizedColors.light_background,
      }),
    ),
    "light",
  );
  const dark = applyStepMinimums(
    withLongHex(
      generateRadixColors({
        appearance: "dark",
        accent: normalizedColors.dark_seed,
        gray: normalizedColors.dark_gray,
        background: normalizedColors.dark_background,
      }),
    ),
    "dark",
  );

  const palette = {
    name: outputName,
    inputs: normalizedColors,
    light: {
      background: light.background,
      brand: {
        radix_brand_foreground: light.accentContrast,
        base_ramp: measureRamp(
          light.accentScale,
          light.background,
          light.accentScale[1],
          light.grayScale,
        ),
        alpha_ramp: light.accentScaleAlpha,
        wide_gamut_ramp: light.accentScaleWideGamut,
        wide_gamut_alpha_ramp: light.accentScaleAlphaWideGamut,
      },
      neutral: {
        base_ramp: measureRamp(
          light.grayScale,
          light.background,
          light.accentScale[1],
          light.grayScale,
        ),
        alpha_ramp: light.grayScaleAlpha,
        wide_gamut_ramp: light.grayScaleWideGamut,
        wide_gamut_alpha_ramp: light.grayScaleAlphaWideGamut,
      },
    },
    dark: {
      background: dark.background,
      brand: {
        radix_brand_foreground: dark.accentContrast,
        base_ramp: measureRamp(
          dark.accentScale,
          dark.background,
          dark.accentScale[1],
          dark.grayScale,
        ),
        alpha_ramp: dark.accentScaleAlpha,
        wide_gamut_ramp: dark.accentScaleWideGamut,
        wide_gamut_alpha_ramp: dark.accentScaleAlphaWideGamut,
      },
      neutral: {
        base_ramp: measureRamp(
          dark.grayScale,
          dark.background,
          dark.accentScale[1],
          dark.grayScale,
        ),
        alpha_ramp: dark.grayScaleAlpha,
        wide_gamut_ramp: dark.grayScaleWideGamut,
        wide_gamut_alpha_ramp: dark.grayScaleAlphaWideGamut,
      },
    },
  };

  const outputPath = path.resolve(outputDirectory, `${outputName}.json`);
  await writeFile(outputPath, `${JSON.stringify(palette, null, 2)}\n`, "utf8");

  return outputPath;
}

//==================================================
// Command Line Entry Point
//==================================================

const isEntryPoint =
  process.argv[1] !== undefined &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;

if (isEntryPoint) {
  const args = process.argv.slice(2);
  const lightSeedIndex = args.indexOf("--light-seed");
  const darkSeedIndex = args.indexOf("--dark-seed");
  const lightGrayIndex = args.indexOf("--light-gray");
  const darkGrayIndex = args.indexOf("--dark-gray");
  const lightBackgroundIndex = args.indexOf("--light-background");
  const darkBackgroundIndex = args.indexOf("--dark-background");
  const brandColorNameIndex = args.indexOf("--brand-color-name");
  const outputDirectoryIndex = args.indexOf("--output-directory");

  const generatedPath = await generate({
    lightSeed: lightSeedIndex === -1 ? "" : args[lightSeedIndex + 1],
    darkSeed: darkSeedIndex === -1 ? undefined : args[darkSeedIndex + 1],
    brandColorName:
      brandColorNameIndex === -1 ? "" : args[brandColorNameIndex + 1],
    lightGray: lightGrayIndex === -1 ? "" : args[lightGrayIndex + 1],
    darkGray: darkGrayIndex === -1 ? "" : args[darkGrayIndex + 1],
    lightBackground:
      lightBackgroundIndex === -1 ? undefined : args[lightBackgroundIndex + 1],
    darkBackground:
      darkBackgroundIndex === -1 ? undefined : args[darkBackgroundIndex + 1],
    outputDirectory:
      outputDirectoryIndex === -1 ? undefined : args[outputDirectoryIndex + 1],
  });

  process.stdout.write(`${generatedPath}\n`);
}
