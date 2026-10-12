import Color from "colorjs.io";

//==================================================
// Inputs
//==================================================

const args = process.argv.slice(2);
const brandColorIndex = args.indexOf("--brand-color");
const chromaRatioIndex = args.indexOf("--chroma-ratio");
const maxChromaIndex = args.indexOf("--max-chroma");
const lightnessIndex = args.indexOf("--lightness");

const brandColor =
  brandColorIndex === -1 ? undefined : args[brandColorIndex + 1];
const chromaRatio =
  chromaRatioIndex === -1 ? 0.12 : Number(args[chromaRatioIndex + 1]);
const maxChroma =
  maxChromaIndex === -1 ? 0.025 : Number(args[maxChromaIndex + 1]);
const lightness =
  lightnessIndex === -1 ? 0.55 : Number(args[lightnessIndex + 1]);

if (!brandColor || !/^#[\da-f]{6}$/i.test(brandColor)) {
  throw new Error("--brand-color must be a six-digit HEX color");
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

const brand = new Color(brandColor).to("oklch");
const brandHue = Number.isNaN(brand.coords[2]) ? 0 : brand.coords[2];
const grayChroma = Math.min(brand.coords[1] * chromaRatio, maxChroma);
const gray = new Color("oklch", [lightness, grayChroma, brandHue]).to("srgb");

let normalizedBrandHex = new Color(brandColor)
  .to("srgb")
  .toString({ format: "hex" })
  .toUpperCase();
let grayHex = gray.toString({ format: "hex" }).toUpperCase();

if (normalizedBrandHex.length === 4) {
  normalizedBrandHex = `#${normalizedBrandHex[1]}${normalizedBrandHex[1]}${normalizedBrandHex[2]}${normalizedBrandHex[2]}${normalizedBrandHex[3]}${normalizedBrandHex[3]}`;
}

if (grayHex.length === 4) {
  grayHex = `#${grayHex[1]}${grayHex[1]}${grayHex[2]}${grayHex[2]}${grayHex[3]}${grayHex[3]}`;
}

//==================================================
// Output
//==================================================

process.stdout.write(
  `${JSON.stringify(
    {
      brand_color: normalizedBrandHex,
      gray_color: grayHex,
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
