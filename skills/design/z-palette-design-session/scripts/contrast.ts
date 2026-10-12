import path from "node:path";
import { pathToFileURL } from "node:url";

//==================================================
// WCAG Contrast
//==================================================

export function wcagContrast(text: string, background: string): number {
  if (!/^#[\da-f]{6}$/i.test(text) || !/^#[\da-f]{6}$/i.test(background)) {
    throw new Error("text and background must be six-digit HEX colors");
  }

  const textRed = Number.parseInt(text.slice(1, 3), 16) / 255;
  const textGreen = Number.parseInt(text.slice(3, 5), 16) / 255;
  const textBlue = Number.parseInt(text.slice(5, 7), 16) / 255;
  const backgroundRed = Number.parseInt(background.slice(1, 3), 16) / 255;
  const backgroundGreen = Number.parseInt(background.slice(3, 5), 16) / 255;
  const backgroundBlue = Number.parseInt(background.slice(5, 7), 16) / 255;

  const textLinearRed = textRed <= 0.04045 ? textRed / 12.92 : ((textRed + 0.055) / 1.055) ** 2.4;
  const textLinearGreen = textGreen <= 0.04045 ? textGreen / 12.92 : ((textGreen + 0.055) / 1.055) ** 2.4;
  const textLinearBlue = textBlue <= 0.04045 ? textBlue / 12.92 : ((textBlue + 0.055) / 1.055) ** 2.4;
  const backgroundLinearRed =
    backgroundRed <= 0.04045 ? backgroundRed / 12.92 : ((backgroundRed + 0.055) / 1.055) ** 2.4;
  const backgroundLinearGreen =
    backgroundGreen <= 0.04045 ? backgroundGreen / 12.92 : ((backgroundGreen + 0.055) / 1.055) ** 2.4;
  const backgroundLinearBlue =
    backgroundBlue <= 0.04045 ? backgroundBlue / 12.92 : ((backgroundBlue + 0.055) / 1.055) ** 2.4;

  const textLuminance = 0.2126 * textLinearRed + 0.7152 * textLinearGreen + 0.0722 * textLinearBlue;
  const backgroundLuminance =
    0.2126 * backgroundLinearRed + 0.7152 * backgroundLinearGreen + 0.0722 * backgroundLinearBlue;
  const lighter = Math.max(textLuminance, backgroundLuminance);
  const darker = Math.min(textLuminance, backgroundLuminance);

  return (lighter + 0.05) / (darker + 0.05);
}

//==================================================
// APCA Contrast
//==================================================

export function apcaContrast(text: string, background: string): number {
  if (!/^#[\da-f]{6}$/i.test(text) || !/^#[\da-f]{6}$/i.test(background)) {
    throw new Error("text and background must be six-digit HEX colors");
  }

  const textRed = Number.parseInt(text.slice(1, 3), 16) / 255;
  const textGreen = Number.parseInt(text.slice(3, 5), 16) / 255;
  const textBlue = Number.parseInt(text.slice(5, 7), 16) / 255;
  const backgroundRed = Number.parseInt(background.slice(1, 3), 16) / 255;
  const backgroundGreen = Number.parseInt(background.slice(3, 5), 16) / 255;
  const backgroundBlue = Number.parseInt(background.slice(5, 7), 16) / 255;

  let textY = 0.2126729 * textRed ** 2.4 + 0.7151522 * textGreen ** 2.4 + 0.072175 * textBlue ** 2.4;
  let backgroundY =
    0.2126729 * backgroundRed ** 2.4 + 0.7151522 * backgroundGreen ** 2.4 + 0.072175 * backgroundBlue ** 2.4;

  textY = textY > 0.022 ? textY : textY + (0.022 - textY) ** 1.414;
  backgroundY = backgroundY > 0.022 ? backgroundY : backgroundY + (0.022 - backgroundY) ** 1.414;

  if (Math.abs(backgroundY - textY) < 0.0005) {
    return 0;
  }

  if (backgroundY > textY) {
    const sapc = (backgroundY ** 0.56 - textY ** 0.57) * 1.14;

    return sapc < 0.1 ? 0 : (sapc - 0.027) * 100;
  }

  const sapc = (backgroundY ** 0.65 - textY ** 0.62) * 1.14;

  return sapc > -0.1 ? 0 : (sapc + 0.027) * 100;
}

//==================================================
// CLI
//==================================================

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;

if (invokedDirectly) {
  const args = process.argv.slice(2);
  const textIndex = args.indexOf("--text");
  const backgroundIndex = args.indexOf("--background");
  const text = textIndex === -1 ? undefined : args[textIndex + 1];
  const background = backgroundIndex === -1 ? undefined : args[backgroundIndex + 1];

  if (!text || !background) {
    throw new Error("--text and --background are required");
  }

  const wcag = wcagContrast(text, background);
  const apca = apcaContrast(text, background);

  process.stdout.write(
    `${JSON.stringify(
      {
        text: text.toUpperCase(),
        background: background.toUpperCase(),
        wcag: Number(wcag.toFixed(2)),
        apca: Number(apca.toFixed(2)),
      },
      null,
      2,
    )}\n`,
  );
}
