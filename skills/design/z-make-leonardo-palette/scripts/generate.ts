import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import {
  BackgroundColor,
  Color as LeonardoColor,
  Theme,
  type ContrastColorValue,
  type CssColor,
} from "@adobe/leonardo-contrast-colors";
import Color from "colorjs.io";
import { makeGray } from "./makeGray.js";

type GenerateOptions = {
  lightSeed: string;
  darkSeed?: string;
  brandColorName: string;
  secondaryColor?: string;
  lightGray?: string;
  darkGray?: string;
  lightBackground?: string;
  darkBackground?: string;
  vibrant?: boolean;
  contrastTargets?: string;
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

//==================================================
// Contrast Targets
//==================================================

// A configs/contrast-targets/*.json file: 12 WCAG 2 contrast ratios against the background, steps 1
// to 12, for each ramp and mode.
type ContrastTargets = Record<"brand" | "neutral", Record<"light" | "dark", number[]>>;

const defaultContrastTargets = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../configs/contrast-targets/default.json",
);

async function readContrastTargets(file: string): Promise<ContrastTargets> {
  const targets = JSON.parse(await readFile(file, "utf8"));

  for (const ramp of ["brand", "neutral"] as const) {
    for (const mode of ["light", "dark"] as const) {
      const ratios = targets[ramp]?.[mode];

      if (!Array.isArray(ratios) || ratios.length !== 12 || !ratios.every((ratio) => typeof ratio === "number" && ratio >= 1)) {
        throw new Error(`${file}: ${ramp}.${mode} must be 12 contrast ratios of at least 1`);
      }
    }
  }

  return targets;
}

// Leonardo names each step after its ratio key.
const ratioKeys = (prefix: string, ratios: number[]) =>
  Object.fromEntries(ratios.map((ratio, index) => [`${prefix}${index + 1}`, ratio]));

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
      // Each channel also needs the alpha that reaches it from the background in its own direction,
      // so a target that is lighter in one channel and darker in another is reproduced.
      const reachAlpha = (target: number, ground: number) =>
        target > ground ? (target - ground) / (rgbPrecision - ground) : target < ground ? (ground - target) / ground : 0;
      const maxAlpha = Math.max(alphaR, alphaG, alphaB, reachAlpha(tr, br), reachAlpha(tg, bg), reachAlpha(tb, bb));

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

// Same text-on-fill choice as the Radix skill and the design session, measured on
// this mode's solid brand fill (step 9). White, unless white text falls below an
// Accessible Perceptual Contrast Algorithm lightness contrast of 40, then black.
function brandForeground(fill: string): string {
  const white = Math.abs(new Color(fill).contrastAPCA(new Color("#FFFFFF")));

  return white < 40 ? "#000000" : "#FFFFFF";
}

//==================================================
// Vibrant
//==================================================

// The lightness at which this chroma and hue reach the target WCAG 2 luminance.
function lightnessFor(chroma: number, hue: number, targetLuminance: number): number {
  let low = 0;
  let high = 1;

  for (let step = 0; step < 40; step += 1) {
    const lightness = (low + high) / 2;
    const color = new Color("oklch", [lightness, chroma, hue]).toGamut({ space: "srgb" });

    if (color.luminance < targetLuminance) {
      low = lightness;
    } else {
      high = lightness;
    }
  }

  return (low + high) / 2;
}

// Each brand step's chroma over the seed's chroma, averaged over Radix generator ramps for
// sample seeds in each hue group. Step 9 is the seed.
const vibrantRatios: Record<string, Record<"light" | "dark", number[]>> = {
  red: { light: [0.02, 0.06, 0.15, 0.26, 0.36, 0.46, 0.58, 0.75, 1, 1, 1, 0.54], dark: [0.2, 0.29, 0.87, 1.12, 1.15, 1.18, 1.23, 1.29, 1, 0.96, 1.34, 0.8] },
  orange: { light: [0.02, 0.09, 0.21, 0.35, 0.48, 0.61, 0.76, 0.98, 1, 1, 0.95, 0.31], dark: [0.17, 0.26, 0.69, 0.94, 1.02, 1.09, 1.16, 1.25, 1, 0.97, 1.33, 0.82] },
  yellow: { light: [0.03, 0.16, 0.46, 0.7, 0.9, 0.94, 0.96, 1.12, 1, 1.05, 1.02, 0.42], dark: [0.11, 0.15, 0.32, 0.45, 0.54, 0.62, 0.73, 0.89, 1, 1, 1.06, 0.64] },
  lime: { light: [0.03, 0.09, 0.34, 0.53, 0.67, 0.76, 0.84, 1.02, 1, 1.01, 0.89, 0.42], dark: [0.11, 0.13, 0.25, 0.37, 0.45, 0.53, 0.61, 0.73, 1, 0.98, 0.98, 0.59] },
  green: { light: [0.05, 0.1, 0.25, 0.39, 0.51, 0.63, 0.77, 1, 1, 1.03, 0.99, 0.48], dark: [0.14, 0.17, 0.37, 0.55, 0.62, 0.68, 0.77, 0.9, 1, 0.91, 1.04, 0.71] },
  mint: { light: [0.07, 0.13, 0.38, 0.6, 0.79, 0.95, 1.15, 1.3, 1, 1, 1.11, 0.65], dark: [0.13, 0.19, 0.42, 0.58, 0.64, 0.7, 0.77, 0.9, 1, 1, 1.08, 0.67] },
  blue: { light: [0.05, 0.09, 0.21, 0.33, 0.43, 0.54, 0.67, 0.9, 1, 1.01, 1, 0.56], dark: [0.19, 0.21, 0.46, 0.64, 0.71, 0.77, 0.85, 1, 1, 0.96, 1, 0.49] },
  sky: { light: [0.08, 0.17, 0.4, 0.62, 0.84, 1.01, 1.21, 1.38, 1, 1.16, 1.35, 0.99], dark: [0.34, 0.4, 0.83, 1, 1.07, 1.12, 1.2, 1.3, 1, 1.03, 1.25, 0.73] },
  purple: { light: [0.02, 0.05, 0.12, 0.22, 0.31, 0.42, 0.56, 0.75, 1, 0.99, 0.97, 0.63], dark: [0.41, 0.53, 1.1, 1.23, 1.25, 1.26, 1.29, 1.34, 1, 0.96, 1.33, 0.76] },
  pink: { light: [0.02, 0.05, 0.16, 0.24, 0.32, 0.4, 0.51, 0.66, 1, 0.99, 0.98, 0.71], dark: [0.24, 0.42, 0.87, 1.17, 1.2, 1.21, 1.23, 1.28, 1, 0.97, 1.33, 0.77] },
};

// The seed's hue group. Seeds at lightness 0.8 or above use the light-seed group for their hue
// where one exists (mint, sky).
function vibrantGroup(lightness: number, hue: number): string {
  if (hue >= 350 || hue < 40) return "red";
  if (hue < 75) return "orange";
  if (hue < 110) return "yellow";
  if (hue < 135) return "lime";
  if (hue < 200) return lightness >= 0.8 ? "mint" : "green";
  if (hue < 260) return lightness >= 0.8 ? "sky" : "blue";
  if (hue < 315) return "purple";
  return "pink";
}

// Sets each brand step's chroma to its group ratio × the seed's chroma, reduced to fit sRGB.
// Each step keeps its WCAG 2 luminance, so it keeps its contrast ratio target.
function applyVibrant(values: ContrastColorValue[], seed: string, mode: "light" | "dark"): ContrastColorValue[] {
  const [seedLightness, seedChroma, seedHue] = new Color(seed).to("oklch").coords;

  if (seedChroma < 0.001) {
    return values;
  }

  const ratios = vibrantRatios[vibrantGroup(seedLightness, seedHue)][mode];

  return values.map((value, index) => {
    const color = new Color(value.value);
    const [, chroma, hue] = color.to("oklch").coords;
    const stepHue = chroma >= 0.01 && !Number.isNaN(hue) ? hue : seedHue;
    const targetChroma = ratios[index] * seedChroma;
    const lightness = lightnessFor(targetChroma, stepHue, color.luminance);
    const adjusted = new Color("oklch", [lightness, targetChroma, stepHue]).toGamut({
      space: "srgb",
    });

    return { ...value, value: adjusted.to("srgb").toString({ format: "hex", collapse: false }).toUpperCase() as CssColor };
  });
}

//==================================================
// Solid Steps
//==================================================

// Step 9 is the seed. Step 10 is its hover, moved by the same amount as Radix's step 10:
// darker under white text, lighter under black text.
function applySolidSteps(values: ContrastColorValue[], seed: string): ContrastColorValue[] {
  const [lightness, chroma, hue] = new Color(seed).to("oklch").coords;
  const darken = brandForeground(seed) === "#FFFFFF";
  const shift = 0.03 / (lightness + 0.1);
  const hover = new Color("oklch", [
    darken ? lightness - shift : lightness + shift,
    darken ? chroma * 0.93 : chroma,
    Number.isNaN(hue) ? 0 : hue,
  ]).toGamut({ space: "srgb" });
  const hoverHex = hover.to("srgb").toString({ format: "hex", collapse: false }).toUpperCase() as CssColor;

  return values.map((value, index) => {
    if (index === 8) return { ...value, value: seed as CssColor };
    if (index === 9) return { ...value, value: hoverHex };
    return value;
  });
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
// and chroma. neutralValues is the neutral ramp for a brand ramp, or null for the neutral ramp.
function applyStepMinimums(
  values: ContrastColorValue[],
  background: string,
  mode: "light" | "dark",
  neutralValues: ContrastColorValue[] | null,
): ContrastColorValue[] {
  const toHex = (color: Color) => color.to("srgb").toString({ format: "hex", collapse: false }).toUpperCase();
  const adjusted = [...values];

  for (const minimum of stepMinimums) {
    if (minimum.brandOnly && neutralValues === null) {
      continue;
    }

    const surfaces = [
      background,
      ...[...values.slice(0, minimum.surfaceSteps), ...(neutralValues ?? []).slice(0, minimum.surfaceSteps)].map(
        (value) => toHex(new Color(value.value)),
      ),
    ];
    const value = adjusted[minimum.index] as ContrastColorValue;
    const step = new Color(value.value).to("oklch");
    let hex = toHex(step);

    if (meetsStepMinimum(hex, surfaces, minimum)) {
      continue;
    }

    while (!meetsStepMinimum(hex, surfaces, minimum) && step.coords[0] > 0 && step.coords[0] < 1) {
      step.coords[0] += mode === "light" ? -0.001 : 0.001;
      hex = toHex(step);
    }

    adjusted[minimum.index] = { ...value, value: hex as CssColor };
  }

  return adjusted;
}

//==================================================
// Entry Point for Palette Generation
//==================================================

export async function generate({
  lightSeed,
  darkSeed = lightSeed,
  brandColorName,
  secondaryColor,
  lightGray,
  darkGray,
  lightBackground = "#FFFFFF",
  darkBackground = "#111111",
  vibrant = false,
  contrastTargets = defaultContrastTargets,
  outputDirectory = process.cwd(),
}: GenerateOptions): Promise<string> {
  const normalizedBrandColorName = brandColorName.toLowerCase();

  if (!/^[a-z][a-z0-9-]*$/.test(normalizedBrandColorName)) {
    throw new Error(
      "brandColorName must start with a letter and use only letters, numbers, and hyphens",
    );
  }

  if (!/^#[\da-f]{6}$/i.test(lightSeed)) {
    throw new Error("lightSeed must be a six-digit HEX color");
  }

  if (!/^#[\da-f]{6}$/i.test(darkSeed)) {
    throw new Error("darkSeed must be a six-digit HEX color");
  }

  if (
    secondaryColor !== undefined &&
    !/^#[\da-f]{6}$/i.test(secondaryColor)
  ) {
    throw new Error("secondaryColor must be a six-digit HEX color");
  }

  if (lightGray !== undefined && !/^#[\da-f]{6}$/i.test(lightGray)) {
    throw new Error("lightGray must be a six-digit HEX color");
  }

  if (darkGray !== undefined && !/^#[\da-f]{6}$/i.test(darkGray)) {
    throw new Error("darkGray must be a six-digit HEX color");
  }

  if (!/^#[\da-f]{6}$/i.test(lightBackground)) {
    throw new Error("lightBackground must be a six-digit HEX color");
  }

  if (!/^#[\da-f]{6}$/i.test(darkBackground)) {
    throw new Error("darkBackground must be a six-digit HEX color");
  }

  const normalizedSecondaryColor = secondaryColor?.toUpperCase();
  const neutralTints = {
    light: lightGray?.toUpperCase() ?? makeGray(lightSeed.toUpperCase()),
    dark: darkGray?.toUpperCase() ?? makeGray(darkSeed.toUpperCase()),
  };
  const normalizedLightBackground = lightBackground.toUpperCase();
  const normalizedDarkBackground = darkBackground.toUpperCase();
  const normalizedColors = {
    light_seed: lightSeed.toUpperCase(),
    dark_seed: darkSeed.toUpperCase(),
    ...(normalizedSecondaryColor
      ? { secondary_color: normalizedSecondaryColor }
      : {}),
    light_gray: neutralTints.light,
    dark_gray: neutralTints.dark,
    light_background: normalizedLightBackground,
    dark_background: normalizedDarkBackground,
  };
  const seedNames =
    normalizedColors.dark_seed === normalizedColors.light_seed
      ? [normalizedColors.light_seed]
      : [normalizedColors.light_seed, normalizedColors.dark_seed];
  const grayNames =
    neutralTints.dark === neutralTints.light ? [neutralTints.light] : [neutralTints.light, neutralTints.dark];
  const outputName = [normalizedBrandColorName, ...seedNames, ...grayNames]
    .map((part) => part.replace("#", ""))
    .join("-")
    .toLowerCase();
  const targets = await readContrastTargets(contrastTargets);
  const brandColorKeys = (seed: string) =>
    [seed, ...(normalizedSecondaryColor ? [normalizedSecondaryColor] : [])] as CssColor[];

  const lightBrand = new LeonardoColor({
    name: "brand",
    colorKeys: brandColorKeys(normalizedColors.light_seed),
    colorSpace: "CAM02p",
    ratios: ratioKeys("b", targets.brand.light),
  });
  const darkBrand = new LeonardoColor({
    name: "brand",
    colorKeys: brandColorKeys(normalizedColors.dark_seed),
    colorSpace: "CAM02p",
    ratios: ratioKeys("b", targets.brand.dark),
  });
  const lightNeutral = new BackgroundColor({
    name: "neutral",
    colorKeys: [neutralTints.light as CssColor],
    colorSpace: "CAM02p",
    ratios: ratioKeys("n", targets.neutral.light),
  });
  const darkNeutral = new BackgroundColor({
    name: "neutral",
    colorKeys: [neutralTints.dark as CssColor],
    colorSpace: "CAM02p",
    ratios: ratioKeys("n", targets.neutral.dark),
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

  const lightBrandValues = applyStepMinimums(
    applySolidSteps(
      vibrant ? applyVibrant(lightBrandOutput.values, normalizedColors.light_seed, "light") : lightBrandOutput.values,
      normalizedColors.light_seed,
    ),
    resolvedLightBackground,
    "light",
    lightNeutralOutput.values,
  );
  const darkBrandValues = applyStepMinimums(
    applySolidSteps(
      vibrant ? applyVibrant(darkBrandOutput.values, normalizedColors.dark_seed, "dark") : darkBrandOutput.values,
      normalizedColors.dark_seed,
    ),
    resolvedDarkBackground,
    "dark",
    darkNeutralOutput.values,
  );
  const lightNeutralValues = applyStepMinimums(lightNeutralOutput.values, resolvedLightBackground, "light", null);
  const darkNeutralValues = applyStepMinimums(darkNeutralOutput.values, resolvedDarkBackground, "dark", null);
  const lightBrandRamp = formatRamp(
    lightBrandValues,
    resolvedLightBackground,
    lightBrandValues,
    lightNeutralValues,
  );
  const darkBrandRamp = formatRamp(
    darkBrandValues,
    resolvedDarkBackground,
    darkBrandValues,
    darkNeutralValues,
  );
  const lightNeutralRamp = formatRamp(
    lightNeutralValues,
    resolvedLightBackground,
    lightBrandValues,
    lightNeutralValues,
  );
  const darkNeutralRamp = formatRamp(
    darkNeutralValues,
    resolvedDarkBackground,
    darkBrandValues,
    darkNeutralValues,
  );
  const lightSolidFill = lightBrandRamp.find((step) => step.role === "solid-fill");
  const darkSolidFill = darkBrandRamp.find((step) => step.role === "solid-fill");

  if (lightSolidFill === undefined || darkSolidFill === undefined) {
    throw new Error("Brand ramp is missing the solid fill");
  }

  const lightMode = {
    background: resolvedLightBackground,
    lightness: lightTheme.lightness,
    brand: {
      brand_foreground: brandForeground(lightSolidFill.color),
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
      brand_foreground: brandForeground(darkSolidFill.color),
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
    inputs: { ...normalizedColors, vibrant, contrast_targets: path.basename(contrastTargets, ".json") },
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
  const lightSeedIndex = args.indexOf("--light-seed");
  const darkSeedIndex = args.indexOf("--dark-seed");
  const brandColorNameIndex = args.indexOf("--brand-color-name");
  const secondaryColorIndex = args.indexOf("--secondary-color");
  const lightGrayIndex = args.indexOf("--light-gray");
  const darkGrayIndex = args.indexOf("--dark-gray");
  const lightBackgroundIndex = args.indexOf("--light-background");
  const darkBackgroundIndex = args.indexOf("--dark-background");
  const outputDirectoryIndex = args.indexOf("--output-directory");
  const contrastTargetsIndex = args.indexOf("--contrast-targets");

  const generatedPath = await generate({
    lightSeed: lightSeedIndex === -1 ? "" : args[lightSeedIndex + 1],
    darkSeed: darkSeedIndex === -1 ? undefined : args[darkSeedIndex + 1],
    brandColorName:
      brandColorNameIndex === -1 ? "" : args[brandColorNameIndex + 1],
    secondaryColor:
      secondaryColorIndex === -1 ? undefined : args[secondaryColorIndex + 1],
    lightGray: lightGrayIndex === -1 ? undefined : args[lightGrayIndex + 1],
    darkGray: darkGrayIndex === -1 ? undefined : args[darkGrayIndex + 1],
    lightBackground:
      lightBackgroundIndex === -1 ? undefined : args[lightBackgroundIndex + 1],
    darkBackground:
      darkBackgroundIndex === -1 ? undefined : args[darkBackgroundIndex + 1],
    vibrant: args.includes("--vibrant"),
    contrastTargets: contrastTargetsIndex === -1 ? undefined : args[contrastTargetsIndex + 1],
    outputDirectory:
      outputDirectoryIndex === -1 ? undefined : args[outputDirectoryIndex + 1],
  });

  process.stdout.write(`${generatedPath}\n`);
}
