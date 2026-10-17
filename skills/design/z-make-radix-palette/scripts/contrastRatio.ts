// WCAG 2 contrast ratio, from the relative luminance of each six-digit HEX color.
export function contrastRatio(a: string, b: string) {
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
