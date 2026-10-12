import { writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import Color from "colorjs.io";
import { generateRadixColors } from "./generateRadixColors.js";

type GenerateOptions = {
  brandColor: string;
  brandColorName: string;
  grayColor: string;
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
  "subtle-surface",
  "surface",
  "normal-interactive-component",
  "hover-interactive-component",
  "active-interactive-component",
  "subtle-border",
  "border",
  "strong-border",
  "primary-fill",
  "primary-hover",
  "medium-contrast-text",
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
// Entry Point for Ramp Generation
//==================================================

export async function generate({
  brandColor,
  brandColorName,
  grayColor,
  lightBackground = "#FFFFFF",
  darkBackground = "#111111",
  outputDirectory = process.cwd(),
}: GenerateOptions): Promise<string> {
  const normalizedBrandColorName = brandColorName.toLowerCase();

  if (!/^[a-z][a-z0-9-]*$/.test(normalizedBrandColorName)) {
    throw new Error(
      "brandColorName must start with a letter and use only letters, numbers, and hyphens",
    );
  }
  const colorInputs = {
    brand_color: brandColor,
    gray_color: grayColor,
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
      let hex = new Color(value)
        .to("srgb")
        .toString({ format: "hex" })
        .toUpperCase();

      if (hex.length === 4) {
        hex = `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
      }

      return [name, hex];
    }),
  ) as Record<keyof typeof colorInputs, string>;

  const outputName =
    `${normalizedBrandColorName}-${normalizedColors.brand_color.slice(1)}-${normalizedColors.gray_color.slice(1)}`.toLowerCase();

  const light = generateRadixColors({
    appearance: "light",
    accent: normalizedColors.brand_color,
    gray: normalizedColors.gray_color,
    background: normalizedColors.light_background,
  });
  const dark = generateRadixColors({
    appearance: "dark",
    accent: normalizedColors.brand_color,
    gray: normalizedColors.gray_color,
    background: normalizedColors.dark_background,
  });

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
  const brandColorIndex = args.indexOf("--brand-color");
  const grayColorIndex = args.indexOf("--gray-color");
  const lightBackgroundIndex = args.indexOf("--light-background");
  const darkBackgroundIndex = args.indexOf("--dark-background");
  const brandColorNameIndex = args.indexOf("--brand-color-name");
  const outputDirectoryIndex = args.indexOf("--output-directory");

  const generatedPath = await generate({
    brandColor: brandColorIndex === -1 ? "" : args[brandColorIndex + 1],
    brandColorName:
      brandColorNameIndex === -1 ? "" : args[brandColorNameIndex + 1],
    grayColor: grayColorIndex === -1 ? "" : args[grayColorIndex + 1],
    lightBackground:
      lightBackgroundIndex === -1 ? undefined : args[lightBackgroundIndex + 1],
    darkBackground:
      darkBackgroundIndex === -1 ? undefined : args[darkBackgroundIndex + 1],
    outputDirectory:
      outputDirectoryIndex === -1 ? undefined : args[outputDirectoryIndex + 1],
  });

  process.stdout.write(`${generatedPath}\n`);
}
