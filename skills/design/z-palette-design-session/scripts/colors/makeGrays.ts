import path from "node:path";
import { pathToFileURL } from "node:url";
import { toHex, toOklch } from "./oklch.js";

//==================================================
// CLI
//==================================================

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;

if (invokedDirectly) {
  const args = process.argv.slice(2);
  const argument = (name: string) => {
    const index = args.indexOf(name);

    return index === -1 ? undefined : args[index + 1];
  };
  const seeds = { light: argument("--light-seed"), dark: argument("--dark-seed") };
  const chromaRatio = Number(argument("--chroma-ratio") ?? 0.12);
  const maxChroma = Number(argument("--max-chroma") ?? 0.025);
  const lightness = Number(argument("--lightness") ?? 0.55);

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

  // Each mode's gray has its seed's hue, and a share of its seed's chroma.
  const gray = (seed: string) => {
    const [, seedChroma, seedHue] = toOklch(seed);

    return toHex(lightness, Math.min(seedChroma * chromaRatio, maxChroma), seedHue);
  };

  process.stdout.write(
    `${JSON.stringify({ light_gray: gray(seeds.light as string), dark_gray: gray(seeds.dark as string) }, null, 2)}\n`,
  );
}
