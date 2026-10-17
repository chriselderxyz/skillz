// Shared by the pages and the scripts. scripts/pages/buildPage.ts inlines this file into each page
// with the export keywords removed.

//==================================================
// Token Mapping
//==================================================

// config: a configs/token-mappings/*.json file. Returns the token groups in display order,
// every token's entry by name, and the file name as a Title Case title.
export const readTokenMapping = (config, name) => ({
	name,
	title: name
		.split("-")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" "),
	description: config.description,
	groups: config.groups.map((group) => ({ label: group.name, tokens: Object.keys(group.tokens) })),
	tokens: Object.assign({}, ...config.groups.map((group) => group.tokens)),
});

//==================================================
// Color Math
//==================================================

const luminance = (hex) => {
	const channels = [1, 3, 5].map((offset) => {
		const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
		return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};

export const contrast = (a, b) => {
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (high + 0.05) / (low + 0.05);
};

// APCA (the contrast method in the WCAG 3 draft), SA98G constants. Returns |Lc|.
const apcaY = (hex) => {
	const [red, green, blue] = [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255);
	return 0.2126729 * red ** 2.4 + 0.7151522 * green ** 2.4 + 0.072175 * blue ** 2.4;
};

// APCA from screen luminances (apcaY of the text and of the background).
const apcaFromY = (textY, backgroundY) => {
	const clamp = (y) => (y > 0.022 ? y : y + (0.022 - y) ** 1.414);
	const text = clamp(textY);
	const background = clamp(backgroundY);
	if (Math.abs(background - text) < 0.0005) return 0;
	if (background > text) {
		const sapc = (background ** 0.56 - text ** 0.57) * 1.14;
		return sapc < 0.1 ? 0 : (sapc - 0.027) * 100;
	}
	const sapc = (background ** 0.65 - text ** 0.62) * 1.14;
	return sapc > -0.1 ? 0 : -(sapc + 0.027) * 100;
};

export const apca = (textHex, backgroundHex) => apcaFromY(apcaY(textHex), apcaY(backgroundHex));

// thresholds: assets/contrast-thresholds.json. Whether a pair meets an element type's minimums.
const meets = (thresholds, element, ratio, lc) => {
	const { wcag, apca: lcMinimum } = thresholds[element];
	return (wcag === null || ratio >= wcag) && lc >= lcMinimum;
};

// Text on a brand seed: white, unless white text falls below APCA Lc 40 on the seed, then black.
// The generator skills pick the text that sets their step 10 hover direction the same way.
export const seedText = (seed) => (apca("#FFFFFF", seed) < 40 ? "#000000" : "#FFFFFF");

// Text on each mode's brand seed.
export const seedForegroundText = (palette) =>
	Object.fromEntries(["light", "dark"].map((mode) => [mode, seedText(palette.seed[mode])]));

//==================================================
// Token Resolution
//==================================================

const modeRef = (mapping, token, mode) => {
	const { ref } = mapping.tokens[token];
	return typeof ref === "string" ? ref : ref[mode];
};

const literalRefs = { white: "#FFFFFF", black: "#000000" };
const signalRamps = { D: "destructive", W: "warning", S: "success" };

// Returns the CSS value of a ref: six-digit HEX, or eight-digit HEX for an alpha step.
const stepHex = (palette, ref, mode) => {
	if (ref === "seed") return palette.seed[mode];
	if (ref === "seed-foreground") return palette.seedForeground[mode];
	if (ref === "selected-background") return palette.backgrounds[mode].color;
	if (literalRefs[ref]) return literalRefs[ref];
	const [, ramp, alpha, step] = /^(B|N|D|W|S)(A?)(\d+)$/.exec(ref);
	const index = Number(step) - 1;
	const ramps = alpha ? palette.alphaRamps : palette.ramps;
	if (ramp === "B") return ramps[`${mode}Brand`][index];
	if (ramp === "N") return ramps[`${mode}Neutral`][index];
	const signal = palette.signals.find((item) => item.key === signalRamps[ramp]);
	return (alpha ? signal.alphaRamps : signal.ramps)[mode][index];
};

// Alpha compositing. overHex paints a CSS HEX value (6 or 8 digits) over an opaque
// ground and returns the opaque six-digit result; opaque colors come back unchanged.
const hexChannels = (hex) => {
	let value = hex.slice(1);
	if (value.length === 3 || value.length === 4) value = [...value].map((char) => char + char).join("");
	const channel = (offset) => Number.parseInt(value.slice(offset, offset + 2), 16);
	return { r: channel(0), g: channel(2), b: channel(4), a: value.length >= 8 ? channel(6) / 255 : 1 };
};
const overHex = (css, ground) => {
	const color = hexChannels(css);
	if (color.a === 1) return css.slice(0, 7).toUpperCase();
	const base = hexChannels(ground);
	const byte = (fg, bg) =>
		Math.min(255, Math.max(0, Math.round(fg * color.a + bg * (1 - color.a))))
			.toString(16)
			.padStart(2, "0");
	return `#${byte(color.r, base.r)}${byte(color.g, base.g)}${byte(color.b, base.b)}`.toUpperCase();
};

// The surface an alpha token is painted on in the mockups. Text sits on its fill
// (secondary-foreground on secondary); sidebar tokens on the sidebar; everything else on
// the page background.
const groundOf = (token, tokens) => {
	if (token === "background") return null;
	if (token.endsWith("-foreground") && token !== "foreground") {
		const fill = token.replace(/-foreground$/, "");
		if (tokens.includes(fill)) return fill;
	}
	if (token.startsWith("sidebar") && token !== "sidebar") return "sidebar";
	return "background";
};

// Pure black or white text for a fill: whichever meets more of the other-text minimums (WCAG 2
// and APCA), with the higher APCA breaking ties.
const blackOrWhite = (fillHex, thresholds) => {
	const { wcag, apca: lcMinimum } = thresholds["other-text"];
	const options = ["white", "black"].map((name) => {
		const ratio = contrast(literalRefs[name], fillHex);
		const lc = apca(literalRefs[name], fillHex);
		return { name, met: Number(wcag === null || ratio >= wcag) + Number(lc >= lcMinimum), lc };
	});
	return options.sort((a, b) => b.met - a.met || b.lc - a.lc)[0].name;
};

// Each token resolves to { ref, css, hex }. css is what the mockups paint (eight-digit
// HEX for alpha steps); hex is the opaque color seen on the token's ground (groundOf).
// "black-or-white" resolves against the token's fill (the same token name without
// "-foreground"), as seen on that fill's ground.
export const resolveMapping = (palette, mapping, mode, thresholds) => {
	const resolved = {};
	const tokens = Object.keys(mapping.tokens);
	const resolve = (token) => {
		if (resolved[token]) return resolved[token];
		const ground = groundOf(token, tokens);
		const groundHex = ground ? resolve(ground).hex : palette.backgrounds[mode].color;
		let ref = modeRef(mapping, token, mode);
		let css;
		if (ref === "black-or-white") {
			ref = blackOrWhite(resolve(token.replace(/-foreground$/, "")).hex, thresholds);
			css = literalRefs[ref];
		} else {
			css = stepHex(palette, ref, mode);
		}
		resolved[token] = { ref, css, hex: overHex(css, groundHex) };
		return resolved[token];
	};
	for (const token of tokens) resolve(token);
	return resolved;
};

// CSS values for the mockups (alpha steps stay see-through).
const resolveCss = (palette, mapping, mode, thresholds) =>
	Object.fromEntries(
		Object.entries(resolveMapping(palette, mapping, mode, thresholds)).map(([token, { css }]) => [token, css]),
	);

// resolved: resolveMapping output. Each check paints the token over the tokens in `against`:
// the first as resolved, then each further token painted over the ones before it.
export const runChecks = (resolved, mapping, thresholds) =>
	Object.fromEntries(
		Object.entries(mapping.tokens).map(([token, { checks }]) => [
			token,
			checks.map(({ against, element }) => {
				const [bottom, ...layers] = against;
				const ground = layers.reduce((below, layer) => overHex(resolved[layer].css, below), resolved[bottom].hex);
				const color = overHex(resolved[token].css, ground);
				const ratio = contrast(color, ground);
				const lc = apca(color, ground);
				const { wcag, apca: lcMinimum } = thresholds[element];
				return {
					against: [...against].reverse().join(" over "),
					element,
					minimum: wcag,
					apcaMinimum: lcMinimum,
					ratio,
					lc,
					pass: meets(thresholds, element, ratio, lc),
				};
			}),
		]),
	);
