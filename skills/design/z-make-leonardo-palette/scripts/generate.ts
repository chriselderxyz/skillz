import { writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  BackgroundColor,
  Color as LeonardoColor,
  Theme,
  type ContrastColorValue,
  type CssColor,
} from "@adobe/leonardo-contrast-colors";
import Color from "colorjs.io";
import { deriveBackground } from "./deriveBackground.js";

type GenerateOptions = {
  brandColor: string;
  brandColorName: string;
  secondaryColor?: string;
  grayColor?: string;
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

const brandLightRatios = {
  b1: 1.03,
  b2: 1.06,
  b3: 1.1,
  b4: 1.17,
  b5: 1.27,
  b6: 1.42,
  b7: 1.71,
  b8: 3.4,
  b9: 4.25,
  b10: 4.7,
  b11: 6,
  b12: 13.5,
};

const brandDarkRatios = {
  b1: 1.04,
  b2: 1.08,
  b3: 1.16,
  b4: 1.32,
  b5: 1.56,
  b6: 1.89,
  b7: 2.45,
  b8: 4,
  b9: 3.4,
  b10: 3.55,
  b11: 8.8,
  b12: 14.2,
};

// Steps 6–8 are borders. Step 8 at 3.4 is a solid fill, which drops the light gray ramp into a dark gray.
const neutralLightRatios = {
  n1: 1.03,
  n2: 1.06,
  n3: 1.1,
  n4: 1.17,
  n5: 1.27,
  n6: 1.37,
  n7: 1.52,
  n8: 1.95,
  n9: 3.3,
  n10: 3.8,
  n11: 6,
  n12: 15.4,
};

const neutralDarkRatios = {
  n1: 1.04,
  n2: 1.08,
  n3: 1.14,
  n4: 1.26,
  n5: 1.4,
  n6: 1.6,
  n7: 1.97,
  n8: 4,
  n9: 3.4,
  n10: 3.55,
  n11: 8.8,
  n12: 15.1,
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
// Color Preparation
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
function formatRamp(
  values: ContrastColorValue[],
  background: string,
  brandValues: ContrastColorValue[],
  neutralValues?: ContrastColorValue[],
): RampStep[] {
  const toHex = (value: string) => {
    const resolvedColor = new Color(value).to("srgb");
    let color = resolvedColor.toString({ format: "hex" }).toUpperCase();

    if (color.length === 4) {
      color = `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`;
    }

    return color;
  };

  const brandStep2Value = brandValues[1];

  if (brandStep2Value === undefined) {
    throw new Error("Brand ramp is missing step 2");
  }

  const backgroundColor = new Color(background);
  const brandStep2Color = new Color(toHex(brandStep2Value.value));
  const white = new Color("#FFFFFF");
  const black = new Color("#000000");
  const neutralReferences = (neutralValues ?? []).map((value, neutralIndex) => {
    return {
      stepNumber: neutralIndex + 1,
      color: new Color(toHex(value.value)),
    };
  });
  const steps: RampStep[] = values.map((value, index) => {
    const color = toHex(value.value);
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

  return steps;
}

//==================================================
// Alpha Ramp
//==================================================

// Same overlay solve as the Radix skill. Each solid step becomes a transparent
// black or white that composites back to that step on the mode background.
function alphaRamp(steps: RampStep[], background: string): string[] {
  return steps.map((step) => {
    const targetRgb = new Color(step.color).to("srgb").coords;
    const backgroundRgb = new Color(background).to("srgb").coords;
    const rgbPrecision = 255;
    const alphaPrecision = 255;
    const [tr, tg, tb] = targetRgb.map((channel: number) => Math.round(channel * rgbPrecision));
    const [br, bg, bb] = backgroundRgb.map((channel: number) =>
      Math.round(channel * rgbPrecision),
    );

    if (
      tr === undefined ||
      tg === undefined ||
      tb === undefined ||
      br === undefined ||
      bg === undefined ||
      bb === undefined
    ) {
      throw new Error("Color is undefined");
    }

    // Lighten the background when any target channel is lighter than it.
    // Otherwise darken the background.
    let desiredRgb = 0;
    if (tr > br) {
      desiredRgb = rgbPrecision;
    } else if (tg > bg) {
      desiredRgb = rgbPrecision;
    } else if (tb > bb) {
      desiredRgb = rgbPrecision;
    }

    const alphaR = (tr - br) / (desiredRgb - br);
    const alphaG = (tg - bg) / (desiredRgb - bg);
    const alphaB = (tb - bb) / (desiredRgb - bb);
    const isPureGray = [alphaR, alphaG, alphaB].every((alpha) => alpha === alphaR);
    let red: number;
    let green: number;
    let blue: number;
    let alpha: number;

    if (isPureGray) {
      red = desiredRgb / rgbPrecision;
      green = red;
      blue = red;
      alpha = alphaR;
    } else {
      const clampRgb = (value: number) =>
        isNaN(value) ? 0 : Math.min(rgbPrecision, Math.max(0, value));
      const clampAlpha = (value: number) =>
        isNaN(value) ? 0 : Math.min(alphaPrecision, Math.max(0, value));
      const maxAlpha = Math.max(alphaR, alphaG, alphaB);

      alpha = clampAlpha(Math.ceil(maxAlpha * alphaPrecision)) / alphaPrecision;
      red = Math.ceil(clampRgb(((br * (1 - alpha) - tr) / alpha) * -1));
      green = Math.ceil(clampRgb(((bg * (1 - alpha) - tg) / alpha) * -1));
      blue = Math.ceil(clampRgb(((bb * (1 - alpha) - tb) / alpha) * -1));

      const blendedRed = blendAlpha(red, alpha, br);
      const blendedGreen = blendAlpha(green, alpha, bg);
      const blendedBlue = blendAlpha(blue, alpha, bb);

      if (desiredRgb === 0) {
        if (tr <= br && tr !== blendedRed) {
          red = tr > blendedRed ? red + 1 : red - 1;
        }

        if (tg <= bg && tg !== blendedGreen) {
          green = tg > blendedGreen ? green + 1 : green - 1;
        }

        if (tb <= bb && tb !== blendedBlue) {
          blue = tb > blendedBlue ? blue + 1 : blue - 1;
        }
      }

      if (desiredRgb === rgbPrecision) {
        if (tr >= br && tr !== blendedRed) {
          red = tr > blendedRed ? red + 1 : red - 1;
        }

        if (tg >= bg && tg !== blendedGreen) {
          green = tg > blendedGreen ? green + 1 : green - 1;
        }

        if (tb >= bb && tb !== blendedBlue) {
          blue = tb > blendedBlue ? blue + 1 : blue - 1;
        }
      }

      red = red / rgbPrecision;
      green = green / rgbPrecision;
      blue = blue / rgbPrecision;
    }

    let hex = new Color("srgb", [red, green, blue], alpha).toString({ format: "hex" });

    if (hex.startsWith("#") && hex.length === 4) {
      hex = `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
    }

    if (hex.startsWith("#") && hex.length === 5) {
      hex = `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}${hex[4]}${hex[4]}`;
    }

    return hex;
  });
}

function blendAlpha(foreground: number, alpha: number, background: number) {
  return Math.round(background * (1 - alpha)) + Math.round(foreground * alpha);
}

//==================================================
// Brand Foreground
//==================================================

// Same text-on-fill choice as the Radix skill, measured on this mode's solid
// brand fill (step 9). White when it clears an Accessible Perceptual Contrast
// Algorithm lightness contrast of 40. Otherwise a dark tint of that fill.
function brandForeground(fill: string): string {
  const fillColor = new Color(fill).to("oklch");
  const white = new Color("oklch", [1, 0, 0]);

  if (Math.abs(white.contrastAPCA(fillColor)) < 40) {
    const chroma = fillColor.coords[1];
    const hue = Number.isNaN(fillColor.coords[2]) ? 0 : fillColor.coords[2];
    let hex = new Color("oklch", [0.25, Math.max(0.08 * chroma, 0.04), hue])
      .to("srgb")
      .toString({ format: "hex" })
      .toUpperCase();

    if (hex.length === 4) {
      hex = `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
    }

    return hex;
  }

  return "#FFFFFF";
}

//==================================================
// Entry Point for Palette Generation
//==================================================

export async function generate({
  brandColor,
  brandColorName,
  secondaryColor,
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

  if (!/^#[\da-f]{6}$/i.test(brandColor)) {
    throw new Error("brandColor must be a six-digit HEX color");
  }

  if (
    secondaryColor !== undefined &&
    !/^#[\da-f]{6}$/i.test(secondaryColor)
  ) {
    throw new Error("secondaryColor must be a six-digit HEX color");
  }

  if (
    grayColor !== undefined &&
    !/^#[\da-f]{6}$/i.test(grayColor)
  ) {
    throw new Error("grayColor must be a six-digit HEX color");
  }

  if (!/^#[\da-f]{6}$/i.test(lightBackground)) {
    throw new Error("lightBackground must be a six-digit HEX color");
  }

  if (!/^#[\da-f]{6}$/i.test(darkBackground)) {
    throw new Error("darkBackground must be a six-digit HEX color");
  }

  const normalizedSecondaryColor = secondaryColor?.toUpperCase();
  const neutralTint =
    grayColor?.toUpperCase() ??
    deriveBackground(brandColor.toUpperCase());
  const normalizedLightBackground = lightBackground.toUpperCase();
  const normalizedDarkBackground = darkBackground.toUpperCase();
  const normalizedColors = {
    brand_color: brandColor.toUpperCase(),
    ...(normalizedSecondaryColor
      ? { secondary_color: normalizedSecondaryColor }
      : {}),
    gray_color: neutralTint,
    light_background: normalizedLightBackground,
    dark_background: normalizedDarkBackground,
  };
  const outputName =
    `${normalizedBrandColorName}-${normalizedColors.brand_color.slice(1)}-${neutralTint.slice(1)}`.toLowerCase();
  const brandColorKeys = [
    normalizedColors.brand_color,
    ...(normalizedSecondaryColor ? [normalizedSecondaryColor] : []),
  ] as CssColor[];
  const neutralColorKey = neutralTint as CssColor;

  const lightBrand = new LeonardoColor({
    name: "brand",
    colorKeys: brandColorKeys,
    colorSpace: "CAM02p",
    ratios: brandLightRatios,
  });
  const darkBrand = new LeonardoColor({
    name: "brand",
    colorKeys: brandColorKeys,
    colorSpace: "CAM02p",
    ratios: brandDarkRatios,
  });
  const lightNeutral = new BackgroundColor({
    name: "neutral",
    colorKeys: [neutralColorKey],
    colorSpace: "CAM02p",
    ratios: neutralLightRatios,
  });
  const darkNeutral = new BackgroundColor({
    name: "neutral",
    colorKeys: [neutralColorKey],
    colorSpace: "CAM02p",
    ratios: neutralDarkRatios,
  });

  // Leonardo's types only list a BackgroundColor here. A hex string is the
  // runtime path that sets lightness from that color and uses it as the page
  // surface. The neutral ramp stays a separate color, tinted by the gray.
  const lightTheme = new Theme({
    colors: [lightNeutral, lightBrand],
    backgroundColor: normalizedLightBackground as unknown as BackgroundColor,
    lightness: 0,
    output: "HEX",
    formula: "wcag2",
  });
  const darkTheme = new Theme({
    colors: [darkNeutral, darkBrand],
    backgroundColor: normalizedDarkBackground as unknown as BackgroundColor,
    lightness: 0,
    output: "HEX",
    formula: "wcag2",
  });

  const [lightBackgroundOutput, lightNeutralOutput, lightBrandOutput] = lightTheme.contrastColors;
  const [darkBackgroundOutput, darkNeutralOutput, darkBrandOutput] = darkTheme.contrastColors;

  if (!lightBrandOutput || !darkBrandOutput || !("values" in lightBrandOutput) || !("values" in darkBrandOutput)) {
    throw new Error("Leonardo did not return the requested brand ramps");
  }

  if (!lightNeutralOutput || !darkNeutralOutput || !("values" in lightNeutralOutput) || !("values" in darkNeutralOutput)) {
    throw new Error("Leonardo did not return the requested neutral ramps");
  }

  const [resolvedLightBackground, resolvedDarkBackground] = [
    lightBackgroundOutput.background,
    darkBackgroundOutput.background,
  ].map((value) => {
    let background = new Color(value)
      .to("srgb")
      .toString({ format: "hex" })
      .toUpperCase();

    if (background.length === 4) {
      background = `#${background[1]}${background[1]}${background[2]}${background[2]}${background[3]}${background[3]}`;
    }

    return background;
  });

  const lightBrandRamp = formatRamp(
    lightBrandOutput.values,
    resolvedLightBackground,
    lightBrandOutput.values,
    lightNeutralOutput.values,
  );
  const darkBrandRamp = formatRamp(
    darkBrandOutput.values,
    resolvedDarkBackground,
    darkBrandOutput.values,
    darkNeutralOutput.values,
  );
  const lightNeutralRamp = formatRamp(
    lightNeutralOutput.values,
    resolvedLightBackground,
    lightBrandOutput.values,
    lightNeutralOutput.values,
  );
  const darkNeutralRamp = formatRamp(
    darkNeutralOutput.values,
    resolvedDarkBackground,
    darkBrandOutput.values,
    darkNeutralOutput.values,
  );
  const lightPrimaryFill = lightBrandRamp.find((step) => step.role === "primary-fill");
  const darkPrimaryFill = darkBrandRamp.find((step) => step.role === "primary-fill");

  if (lightPrimaryFill === undefined || darkPrimaryFill === undefined) {
    throw new Error("Brand ramp is missing the primary fill");
  }

  const lightMode = {
    background: resolvedLightBackground,
    lightness: lightTheme.lightness,
    brand: {
      brand_foreground: brandForeground(lightPrimaryFill.color),
      base_ramp: lightBrandRamp,
      alpha_ramp: alphaRamp(lightBrandRamp, resolvedLightBackground),
    },
    neutral: {
      base_ramp: lightNeutralRamp,
      alpha_ramp: alphaRamp(lightNeutralRamp, resolvedLightBackground),
    },
  };
  const darkMode = {
    background: resolvedDarkBackground,
    lightness: darkTheme.lightness,
    brand: {
      brand_foreground: brandForeground(darkPrimaryFill.color),
      base_ramp: darkBrandRamp,
      alpha_ramp: alphaRamp(darkBrandRamp, resolvedDarkBackground),
    },
    neutral: {
      base_ramp: darkNeutralRamp,
      alpha_ramp: alphaRamp(darkNeutralRamp, resolvedDarkBackground),
    },
  };

  const palette = {
    name: outputName,
    inputs: normalizedColors,
    light: lightMode,
    dark: darkMode,
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
  const brandColorNameIndex = args.indexOf("--brand-color-name");
  const secondaryColorIndex = args.indexOf("--secondary-color");
  const grayColorIndex = args.indexOf("--gray-color");
  const lightBackgroundIndex = args.indexOf("--light-background");
  const darkBackgroundIndex = args.indexOf("--dark-background");
  const outputDirectoryIndex = args.indexOf("--output-directory");

  const generatedPath = await generate({
    brandColor: brandColorIndex === -1 ? "" : args[brandColorIndex + 1],
    brandColorName:
      brandColorNameIndex === -1 ? "" : args[brandColorNameIndex + 1],
    secondaryColor:
      secondaryColorIndex === -1 ? undefined : args[secondaryColorIndex + 1],
    grayColor:
      grayColorIndex === -1
        ? undefined
        : args[grayColorIndex + 1],
    lightBackground:
      lightBackgroundIndex === -1 ? undefined : args[lightBackgroundIndex + 1],
    darkBackground:
      darkBackgroundIndex === -1 ? undefined : args[darkBackgroundIndex + 1],
    outputDirectory:
      outputDirectoryIndex === -1 ? undefined : args[outputDirectoryIndex + 1],
  });

  process.stdout.write(`${generatedPath}\n`);
}
