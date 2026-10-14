const tokenGroups = [
	{
		label: "Normal",
		tokens: [
			"background",
			"foreground",
			"primary",
			"primary-foreground",
			"secondary",
			"secondary-foreground",
			"accent",
			"accent-foreground",
			"muted",
			"muted-foreground",
			"border",
			"input",
			"ring",
		],
	},
	{
		label: "Sidebar",
		tokens: [
			"sidebar",
			"sidebar-foreground",
			"sidebar-primary",
			"sidebar-primary-foreground",
			"sidebar-accent",
			"sidebar-accent-foreground",
			"sidebar-border",
			"sidebar-ring",
		],
	},
	{ label: "Cards", tokens: ["card", "card-foreground"] },
	{ label: "Popovers", tokens: ["popover", "popover-foreground"] },
	{ label: "Charts", tokens: ["chart-primary"] },
	{
		label: "Signals",
		tokens: [
			"destructive",
			"destructive-fill",
			"destructive-fill-foreground",
			"warning",
			"warning-fill",
			"warning-fill-foreground",
			"success",
			"success-fill",
			"success-fill-foreground",
		],
	},
];

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

const contrast = (a, b) => {
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (high + 0.05) / (low + 0.05);
};

// APCA (the contrast method in the WCAG 3 draft), SA98G constants. Returns |Lc|.
// Lc 90 is preferred for body text, 75 is the floor for fluent reading text,
// 60 for other content text, 45 for large headings and non-text.
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

const apca = (textHex, backgroundHex) => apcaFromY(apcaY(textHex), apcaY(backgroundHex));

const formatRatio = (ratio) => `${ratio.toFixed(2).replace(/\.?0+$/, "")}:1`;

// Text on a brand seed. White for a deep seed, light neutral step 12 for a
// light seed. Use whichever passes WCAG 4.5:1 and APCA Lc 75 on the seed.
// When both pass, or neither passes, use the higher APCA.
const seedForegroundText = (palette) => {
	const options = ["#FFFFFF", palette.ramps.lightNeutral[11]].map((text) => ({
		text,
		wcag: contrast(text, palette.seed),
		lc: apca(text, palette.seed),
	}));
	const passing = options.filter((option) => option.wcag >= TEXT && option.lc >= SEED_TEXT_LC);
	return (passing.length > 0 ? passing : options).sort((a, b) => b.lc - a.lc)[0].text;
};

//==================================================
// Token Resolution
//==================================================

const signalKeyOf = (token) =>
	["destructive", "warning", "success"].find((key) => token.startsWith(key));

const modeRef = (scheme, token, mode) => {
	const ref = scheme.tokens[token];
	return typeof ref === "string" ? ref : ref[mode];
};

// Named literals, not ramp steps. white matches the generator's light background;
// black is pure #000000, darker than the generator's dark background (#111111).
const literalRefs = { white: "#FFFFFF", black: "#000000" };

// Returns the CSS value of a ref: six-digit HEX, or eight-digit HEX for an alpha step.
const stepHex = (palette, ref, mode, token) => {
	if (ref === "seed") return palette.seed;
	if (ref === "seed-foreground") return palette.seedForeground;
	if (ref === "selected-background") return palette.backgrounds[mode].color;
	if (literalRefs[ref]) return literalRefs[ref];
	const [, ramp, alpha, step] = /^([BNS])(A?)(\d+)$/.exec(ref);
	const index = Number(step) - 1;
	const ramps = alpha ? palette.alphaRamps : palette.ramps;
	if (ramp === "B") return ramps[`${mode}Brand`][index];
	if (ramp === "N") return ramps[`${mode}Neutral`][index];
	const signal = palette.signals.find((item) => item.key === signalKeyOf(token));
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
// the page background. Contrast checks paint a token over whatever it is measured against.
const groundOf = (token, tokens) => {
	if (token === "background") return null;
	if (token.endsWith("-foreground") && token !== "foreground") {
		const fill = token.replace(/-foreground$/, "");
		if (tokens.includes(fill)) return fill;
	}
	if (token.startsWith("sidebar") && token !== "sidebar") return "sidebar";
	return "background";
};

// Pure black or white text for a fill: whichever passes WCAG 4.5:1 and APCA Lc 60;
// if both pass, the higher APCA wins.
const blackOrWhite = (fillHex) => {
	const options = ["white", "black"].map((name) => ({
		name,
		wcag: contrast(literalRefs[name], fillHex),
		lc: apca(literalRefs[name], fillHex),
	}));
	const passing = options.filter((option) => option.wcag >= TEXT && option.lc >= OTHER_TEXT_LC);
	return (passing.length > 0 ? passing : options).sort((a, b) => b.lc - a.lc)[0].name;
};

// Each token resolves to { ref, css, hex }. css is what the mockups paint (eight-digit
// HEX for alpha steps); hex is the opaque color seen on the token's ground (groundOf).
// "black-or-white" resolves against the token's fill (the same token name without
// "-foreground"), as seen on that fill's ground.
const resolveScheme = (palette, scheme, mode) => {
	const resolved = {};
	const tokens = Object.keys(scheme.tokens);
	const resolve = (token) => {
		if (resolved[token]) return resolved[token];
		const ground = groundOf(token, tokens);
		const groundHex = ground ? resolve(ground).hex : palette.backgrounds[mode].color;
		let ref = modeRef(scheme, token, mode);
		let css;
		if (ref === "black-or-white") {
			ref = blackOrWhite(resolve(token.replace(/-foreground$/, "")).hex);
			css = literalRefs[ref];
		} else {
			css = stepHex(palette, ref, mode, token);
		}
		resolved[token] = { ref, css, hex: overHex(css, groundHex) };
		return resolved[token];
	};
	for (const token of tokens) resolve(token);
	return resolved;
};

// Opaque colors as seen on each token's ground.
const resolveTokens = (palette, scheme, mode) =>
	Object.fromEntries(
		Object.entries(resolveScheme(palette, scheme, mode)).map(([token, { hex }]) => [token, hex]),
	);

// CSS values for the mockups (alpha steps stay see-through).
const resolveCss = (palette, scheme, mode) =>
	Object.fromEntries(
		Object.entries(resolveScheme(palette, scheme, mode)).map(([token, { css }]) => [token, css]),
	);

// resolved: resolveScheme output. An alpha token is painted over the color it is
// measured against.
const runChecks = (resolved, mode = "dark") => {
	const results = {};
	for (const [token, checks] of Object.entries(tokenChecks)) {
		results[token] = checks.map(([against, minimum, apcaMinimum]) => {
			const ground = resolved[against].hex;
			const color = overHex(resolved[token].css, ground);
			const ratio = contrast(color, ground);
			const lc = apca(color, ground);
			return {
				against,
				minimum,
				apcaMinimum,
				ratio,
				lc,
				pass: minimum === null ? null : ratio >= minimum && (!apcaMinimum || lc >= apcaMinimum),
			};
		});
	}
	return results;
};
