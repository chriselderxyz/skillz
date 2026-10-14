// [measured against, minimum WCAG 2 ratio or null for informational, minimum APCA Lc]
// Minimums from the Minimum Contrast Thresholds table in references/color-design-tokens.md.
const TEXT = 4.5;
const NON_TEXT = 3;
const BODY_TEXT_LC = 75;
const SEED_TEXT_LC = 75;
const OTHER_TEXT_LC = 60;
const NON_TEXT_LC = 45;
const tokenChecks = {
	foreground: [["background", TEXT, BODY_TEXT_LC], ["card", TEXT, BODY_TEXT_LC], ["popover", TEXT, BODY_TEXT_LC]],
	"primary-foreground": [["primary", TEXT, SEED_TEXT_LC]],
	"secondary-foreground": [["secondary", TEXT, OTHER_TEXT_LC]],
	"accent-foreground": [["accent", TEXT, OTHER_TEXT_LC]],
	"muted-foreground": [["muted", TEXT, OTHER_TEXT_LC], ["background", TEXT, OTHER_TEXT_LC], ["card", TEXT, OTHER_TEXT_LC], ["popover", TEXT, OTHER_TEXT_LC]],
	border: [["background", null]],
	input: [["background", NON_TEXT, NON_TEXT_LC], ["card", NON_TEXT, NON_TEXT_LC], ["sidebar", NON_TEXT, NON_TEXT_LC], ["popover", NON_TEXT, NON_TEXT_LC]],
	ring: [["background", NON_TEXT, NON_TEXT_LC], ["card", NON_TEXT, NON_TEXT_LC]],
	"sidebar-foreground": [["sidebar", TEXT, OTHER_TEXT_LC]],
	"sidebar-primary-foreground": [["sidebar-primary", TEXT, SEED_TEXT_LC]],
	"sidebar-accent-foreground": [["sidebar-accent", TEXT, OTHER_TEXT_LC]],
	"sidebar-border": [["sidebar", null]],
	"sidebar-ring": [["sidebar", NON_TEXT, NON_TEXT_LC]],
	"card-foreground": [["card", TEXT, BODY_TEXT_LC]],
	"popover-foreground": [["popover", TEXT, BODY_TEXT_LC]],
	"chart-primary": [["card", NON_TEXT, NON_TEXT_LC], ["background", NON_TEXT, NON_TEXT_LC], ["muted", NON_TEXT, NON_TEXT_LC]],
	"destructive-fill-foreground": [["destructive-fill", TEXT, OTHER_TEXT_LC]],
	"warning-fill-foreground": [["warning-fill", TEXT, OTHER_TEXT_LC]],
	"success-fill-foreground": [["success-fill", TEXT, OTHER_TEXT_LC]],
	"destructive-fill": [["background", null]],
	"warning-fill": [["background", null]],
	"success-fill": [["background", null]],
	primary: [["background", null], ["card", null]],
	secondary: [["background", null]],
	accent: [["background", null]],
	muted: [["background", null]],
	sidebar: [["background", null]],
	"sidebar-primary": [["sidebar", null]],
	"sidebar-accent": [["sidebar", null]],
	card: [["background", null]],
	popover: [["background", null]],
	destructive: [["background", TEXT, OTHER_TEXT_LC], ["card", TEXT, OTHER_TEXT_LC], ["popover", TEXT, OTHER_TEXT_LC]],
	warning: [["background", TEXT, OTHER_TEXT_LC], ["card", TEXT, OTHER_TEXT_LC]],
	success: [["background", TEXT, OTHER_TEXT_LC], ["card", TEXT, OTHER_TEXT_LC]],
};
