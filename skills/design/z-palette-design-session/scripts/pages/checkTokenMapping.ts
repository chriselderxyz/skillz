import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  apca,
  contrast,
  readTokenMapping,
  resolveMapping,
  runChecks,
  seedForegroundText,
} from "../../assets/tokenResolution.js";
import { loadPalettes } from "./loadPalettes.js";

const skillDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

//==================================================
// Inputs
//==================================================

const args = process.argv.slice(2);
const argument = (name: string) => {
  const index = args.indexOf(name);

  return index === -1 ? undefined : args[index + 1];
};
const palettesPath = argument("--palettes");
const tokenMappingPath = argument("--token-mapping");

if (!palettesPath || !tokenMappingPath) {
  throw new Error("--palettes and --token-mapping are required");
}

const thresholds = JSON.parse(
  await readFile(path.join(skillDirectory, "assets/contrast-thresholds.json"), "utf8"),
);
const tokenMapping = readTokenMapping(
  JSON.parse(await readFile(tokenMappingPath, "utf8")),
  path.basename(tokenMappingPath, ".json"),
);
const palettes = await loadPalettes(palettesPath);

//==================================================
// Checks
//==================================================

const round = (value: number) => Number(value.toFixed(2));

const results = palettes.map((palette) => {
  const seedForeground = seedForegroundText(palette, thresholds);
  const withSeedForeground = { ...palette, seedForeground };
  const failures = [];
  let passed = 0;
  let total = 0;

  for (const mode of ["light", "dark"]) {
    const checks = runChecks(resolveMapping(withSeedForeground, tokenMapping, mode, thresholds), tokenMapping, thresholds);

    for (const [token, tokenResults] of Object.entries(checks)) {
      for (const check of tokenResults) {
        total += 1;

        if (check.pass) {
          passed += 1;
          continue;
        }

        failures.push({
          mode,
          token,
          against: check.against,
          element: check.element,
          wcag: round(check.ratio),
          apca: round(check.lc),
          minimum_wcag: check.minimum,
          minimum_apca: check.apcaMinimum,
        });
      }
    }
  }

  return {
    name: palette.name,
    generator: palette.generator.toLowerCase(),
    seed_foreground: Object.fromEntries(
      (["light", "dark"] as const).map((mode) => [
        mode,
        {
          seed: palette.seed[mode],
          color: seedForeground[mode],
          wcag: round(contrast(seedForeground[mode], palette.seed[mode])),
          apca: round(apca(seedForeground[mode], palette.seed[mode])),
        },
      ]),
    ),
    passed,
    total,
    failures,
  };
});

process.stdout.write(`${JSON.stringify({ token_mapping: tokenMapping.name, palettes: results }, null, 2)}\n`);
