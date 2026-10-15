import Color from "colorjs.io";

//==================================================
// Inputs
//==================================================

const args = process.argv.slice(2);
const lightSeedIndex = args.indexOf("--light-seed");
const darkSeedIndex = args.indexOf("--dark-seed");
const chromaRatioIndex = args.indexOf("--chroma-ratio");
const maxChromaIndex = args.indexOf("--max-chroma");
const lightnessIndex = args.indexOf("--lightness");

const seeds = {
  light: lightSeedIndex === -1 ? undefined : args[lightSeedIndex + 1],
  dark: darkSeedIndex === -1 ? undefined : args[darkSeedIndex + 1],
};
const chromaRatio =
  chromaRatioIndex === -1 ? 0.12 : Number(args[chromaRatioIndex + 1]);
const maxChroma =
  maxChromaIndex === -1 ? 0.025 : Number(args[maxChromaIndex + 1]);
const lightness =
  lightnessIndex === -1 ? 0.55 : Number(args[lightnessIndex + 1]);

for (const [mode, seed] of Object.entries(seeds)) {
  if (!seed || !/^#[\da-f]{6}$/i.test(seed)) {
    throw new Error(`--${mode}-seed must be a six-digit HEX color`);
  }
}

if (!Number.isFinite(chromaRatio) || chromaRatio < 0 || chromaRatio > 1) {
  throw new Error("--chroma-ratio must be between 0 and 1");
}

if (!Number.isFinite(maxChroma) || maxChroma < 0 || maxChroma > 0.4) {
  throw new Error("--max-chroma must be between 0 and 0.4");
}

if (!Number.isFinite(lightness) || lightness < 0 || lightness > 1) {
  throw new Error("--lightness must be between 0 and 1");
}

//==================================================
// Gray Selection
//==================================================

// Each mode's gray has its seed's hue, and a share of its seed's chroma.
function makeGray(seed: string): string {
  const color = new Color(seed).to("oklch");
  const hue = Number.isNaN(color.coords[2]) ? 0 : color.coords[2];
  const grayChroma = Math.min(color.coords[1] * chromaRatio, maxChroma);
  const grayHex = new Color("oklch", [lightness, grayChroma, hue])
    .to("srgb")
    .toString({ format: "hex" })
    .toUpperCase();

  return grayHex.length === 4
    ? `#${grayHex[1]}${grayHex[1]}${grayHex[2]}${grayHex[2]}${grayHex[3]}${grayHex[3]}`
    : grayHex;
}

//==================================================
// Output
//==================================================

process.stdout.write(
  `${JSON.stringify(
    {
      light_gray: makeGray(seeds.light as string),
      dark_gray: makeGray(seeds.dark as string),
      knobs: {
        chroma_ratio: chromaRatio,
        max_chroma: maxChroma,
        lightness,
      },
    },
    null,
    2,
  )}\n`,
);
