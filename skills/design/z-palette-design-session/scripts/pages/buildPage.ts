import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readTokenMapping } from "../../assets/tokenResolution.js";
import { loadPalettes } from "./loadPalettes.js";

const skillDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const assetPath = (name: string) => path.join(skillDirectory, "assets", name);

//==================================================
// Inputs
//==================================================

const args = process.argv.slice(2);
const argument = (name: string) => {
  const index = args.indexOf(name);

  return index === -1 ? undefined : args[index + 1];
};
const page = argument("--page");
const palettesPath = argument("--palettes");
const tokenMappingPath = argument("--token-mapping");
const summary = argument("--summary") ?? "";
const outputPath = argument("--output");
const paletteName = argument("--palette");
const generator = argument("--generator");

if (page !== "design-session" && page !== "export") {
  throw new Error("--page must be design-session or export");
}

if (!palettesPath || !tokenMappingPath || !outputPath) {
  throw new Error("--palettes, --token-mapping, and --output are required");
}

if (page === "export" && (!paletteName || !generator)) {
  throw new Error("--palette and --generator are required for the export page");
}

//==================================================
// Page Data
//==================================================

const palettes = await loadPalettes(palettesPath);
const tokenMapping = readTokenMapping(
  JSON.parse(await readFile(tokenMappingPath, "utf8")),
  path.basename(tokenMappingPath, ".json"),
);
const thresholds = JSON.parse(await readFile(assetPath("contrast-thresholds.json"), "utf8"));

function paletteBlock() {
  if (page === "design-session") {
    const withoutWideGamut = palettes.map(({ wideGamutRamps, wideGamutAlphaRamps, ...palette }) => ({
      ...palette,
      signals: palette.signals.map(({ wideGamutRamps, wideGamutAlphaRamps, ...signal }) => signal),
    }));

    return ["PALETTE_DATA", `const paletteData = ${JSON.stringify(withoutWideGamut, null, "\t")};`];
  }

  const selected = palettes.find(
    (palette) => palette.name === paletteName && palette.generator.toLowerCase() === generator?.toLowerCase(),
  );

  if (!selected) {
    throw new Error(`The palette file has no ${paletteName} palette from ${generator}`);
  }

  return ["PALETTE", `const palette = ${JSON.stringify(selected, null, "\t")};`];
}

//==================================================
// Injection
//==================================================

const replaceBlock = (html: string, start: string, end: string, content: string) => {
  const from = html.indexOf(start);
  const to = html.indexOf(end);

  if (from === -1 || to < from) {
    throw new Error(`The template is missing ${start}`);
  }

  return `${html.slice(0, from + start.length)}\n${content}\n${html.slice(to)}`;
};

const [paletteMarker, paletteContent] = paletteBlock();
const tokenResolution = (await readFile(assetPath("tokenResolution.js"), "utf8")).replace(/^export /gm, "");
const blocks: [string, string, string][] = [
  ["/* @@PAGE_STYLES_START */", "/* @@PAGE_STYLES_END */", await readFile(assetPath("pageStyles.css"), "utf8")],
  ["<!-- @@SUMMARY_START -->", "<!-- @@SUMMARY_END -->", `<p class="page-intro">${summary}</p>`],
  [`// @@${paletteMarker}_START`, `// @@${paletteMarker}_END`, paletteContent],
  ["// @@TOKEN_MAPPING_START", "// @@TOKEN_MAPPING_END", `const tokenMapping = ${JSON.stringify(tokenMapping, null, "\t")};`],
  ["// @@CONTRAST_THRESHOLDS_START", "// @@CONTRAST_THRESHOLDS_END", `const contrastThresholds = ${JSON.stringify(thresholds, null, "\t")};`],
  ["// @@TOKEN_RESOLUTION_START", "// @@TOKEN_RESOLUTION_END", tokenResolution],
];

let html = await readFile(assetPath(`${page}.html`), "utf8");

for (const [start, end, content] of blocks) {
  html = replaceBlock(html, start, end, content);
}

await writeFile(outputPath, html, "utf8");
process.stdout.write(`${path.resolve(outputPath)}\n`);
