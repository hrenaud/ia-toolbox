import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Contrast guarantees for the colours actually declared in the stylesheets.
 *
 * The colours are read out of the CSS rather than restated here, because a test
 * holding its own copies of the hex values asserts arithmetic and not the app:
 * editing `theme.css` to a failing colour would leave it green. The pairs are
 * still enumerated by hand — resolving the real cascade is not worth it, and an
 * explicit pair cannot produce a false pass.
 */

// Read from the project root: the jsdom environment resolves `import.meta.url`
// to an http URL, which `readFileSync` rejects.
const THEME_CSS = readFileSync(resolve("src/app/theme.css"), "utf8");
const CONVERSION_CSS = readFileSync(
  resolve("src/features/conversion/ConversionPage.css"),
  "utf8",
);

/**
 * Read a declaration from the stylesheet.
 *
 * A selector can appear in several rules — `.warning` is in a shared layout
 * rule and again in its own colour rule — so every matching rule is scanned and
 * the last declaration wins, as the cascade would have it.
 */
function declaredValue(
  css: string,
  selector: string,
  property: string,
): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matchesSelector = new RegExp(`(?:^|,)\\s*${escaped}\\s*(?:,|$)`);
  const declares = new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+)`);

  let declaration: RegExpExecArray | null = null;
  let matchedAnyRule = false;
  for (const rule of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    if (!matchesSelector.test(rule[1].trim())) continue;
    matchedAnyRule = true;
    declaration = declares.exec(rule[2]) ?? declaration;
  }

  if (!matchedAnyRule) throw new Error(`no rule matching "${selector}"`);
  if (!declaration) throw new Error(`"${selector}" declares no ${property}`);

  const value = declaration[1].trim();
  if (!/^#[0-9a-f]{6}$/i.test(value)) {
    throw new Error(
      `"${selector}" ${property} is "${value}", not a 6-digit hex colour`,
    );
  }
  return value;
}

/** WCAG 2.1 relative luminance. */
function relativeLuminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const channel = parseInt(hex.slice(i, i + 2), 16) / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(foreground: string, background: string): number {
  const a = relativeLuminance(foreground);
  const b = relativeLuminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const lightBackground = declaredValue(THEME_CSS, ":root", "--background");
const lightSurface = declaredValue(THEME_CSS, ":root", "--surface");
const darkBackground = declaredValue(
  THEME_CSS,
  ':root[data-theme="dark"]',
  "--background",
);

// 4.5:1 is the AA threshold for normal-size text. None of these qualifies as
// "large" (>=24px, or >=18.66px bold): the badges are 0.8rem/600 and the
// warning is 0.95rem, so the relaxed 3:1 threshold does not apply.
const textPairs: ReadonlyArray<[string, string, string]> = [
  [".warning", "color", "background"],
  [".status-running", "color", "background"],
  [".status-success", "color", "background"],
  [".status-error", "color", "background"],
  [".status-queued", "color", "background"],
];

describe("declared text colours meet WCAG AA", () => {
  it.each(textPairs)(
    "%s",
    (selector, foregroundProperty, backgroundProperty) => {
      const foreground = declaredValue(
        CONVERSION_CSS,
        selector,
        foregroundProperty,
      );
      const background = declaredValue(
        CONVERSION_CSS,
        selector,
        backgroundProperty,
      );
      expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it(".status-badge.unsupported", () => {
    const foreground = declaredValue(
      CONVERSION_CSS,
      ".status-badge.unsupported",
      "color",
    );
    const background = declaredValue(
      CONVERSION_CSS,
      ".status-badge.unsupported",
      "background",
    );
    expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
  });
});

// WCAG 1.4.11: 3:1 for the visual boundary of a UI component. The light border
// sits on both the page background and the raised surface, so both must clear.
describe("declared border colours meet the non-text threshold", () => {
  it("light border on background", () => {
    const border = declaredValue(THEME_CSS, ":root", "--border");
    expect(contrastRatio(border, lightBackground)).toBeGreaterThanOrEqual(3);
  });

  it("light border on surface", () => {
    const border = declaredValue(THEME_CSS, ":root", "--border");
    expect(contrastRatio(border, lightSurface)).toBeGreaterThanOrEqual(3);
  });

  it("dark border on background", () => {
    const border = declaredValue(
      THEME_CSS,
      ':root[data-theme="dark"]',
      "--border",
    );
    expect(contrastRatio(border, darkBackground)).toBeGreaterThanOrEqual(3);
  });
});

describe("declared body text meets WCAG AA", () => {
  it.each([
    [":root", "light"],
    [':root[data-theme="dark"]', "dark"],
  ])("%s text and muted text on background", (selector) => {
    const background = declaredValue(THEME_CSS, selector, "--background");
    expect(
      contrastRatio(declaredValue(THEME_CSS, selector, "--text"), background),
    ).toBeGreaterThanOrEqual(4.5);
    expect(
      contrastRatio(declaredValue(THEME_CSS, selector, "--muted"), background),
    ).toBeGreaterThanOrEqual(4.5);
  });
});
