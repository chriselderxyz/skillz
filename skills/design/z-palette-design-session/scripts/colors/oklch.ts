import path from "node:path";
import { pathToFileURL } from "node:url";

//==================================================
// OKLCH
//==================================================

const toLinear = (channel: number) =>
  channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
const toEncoded = (channel: number) =>
  channel <= 0.0031308 ? channel * 12.92 : 1.055 * channel ** (1 / 2.4) - 0.055;

// Returns [lightness from 0 to 1, chroma, hue in degrees].
export function toOklch(hex: string): [number, number, number] {
  const [red, green, blue] = [1, 3, 5].map((offset) =>
    toLinear(Number.parseInt(hex.slice(offset, offset + 2), 16) / 255),
  );
  const long = Math.cbrt(0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue);
  const medium = Math.cbrt(0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue);
  const short = Math.cbrt(0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue);
  const lightness = 0.2104542553 * long + 0.793617785 * medium - 0.0040720468 * short;
  const a = 1.9779984951 * long - 2.428592205 * medium + 0.4505937099 * short;
  const b = 0.0259040371 * long + 0.7827717662 * medium - 0.808675766 * short;

  return [lightness, Math.hypot(a, b), ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360];
}

// Linear sRGB channels for an OKLCH color, unclamped.
function toLinearSrgb(lightness: number, chroma: number, hue: number): number[] {
  const a = chroma * Math.cos((hue * Math.PI) / 180);
  const b = chroma * Math.sin((hue * Math.PI) / 180);
  const long = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const short = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;

  return [
    4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
    -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
    -0.0041960863 * long - 0.7034186147 * medium + 1.707614701 * short,
  ];
}

// The most chroma sRGB holds at this lightness and hue.
export function maxChroma(lightness: number, hue: number): number {
  let low = 0;
  let high = 0.4;

  for (let step = 0; step < 30; step += 1) {
    const chroma = (low + high) / 2;

    if (toLinearSrgb(lightness, chroma, hue).every((channel) => channel >= -0.0001 && channel <= 1.0001)) {
      low = chroma;
    } else {
      high = chroma;
    }
  }

  return low;
}

export function toHex(lightness: number, chroma: number, hue: number): string {
  const channels = toLinearSrgb(lightness, chroma, hue);

  return `#${channels
    .map((channel) =>
      Math.round(toEncoded(Math.min(1, Math.max(0, channel))) * 255)
        .toString(16)
        .padStart(2, "0"),
    )
    .join("")}`.toUpperCase();
}

// A color's chroma as a share of the most chroma sRGB holds at its lightness and hue.
export function relativeChroma(hex: string): number {
  const [lightness, chroma, hue] = toOklch(hex);
  const most = maxChroma(lightness, hue);

  return most === 0 ? 0 : chroma / most;
}

export function describe(hex: string) {
  const [lightness, chroma, hue] = toOklch(hex);
  const round = (value: number, digits: number) => Number(value.toFixed(digits));

  return {
    color: hex,
    lightness: round(lightness, 3),
    chroma: round(chroma, 3),
    hue: round(hue, 2),
    relative_chroma: round(relativeChroma(hex), 3),
  };
}

//==================================================
// CLI
//==================================================

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;

if (invokedDirectly) {
  const args = process.argv.slice(2);
  const color = args.includes("--color") ? args[args.indexOf("--color") + 1] : undefined;

  if (color === undefined || !/^#[\da-f]{6}$/i.test(color)) {
    throw new Error("--color must be a six-digit HEX color");
  }

  process.stdout.write(`${JSON.stringify(describe(color.toUpperCase()), null, 2)}\n`);
}
