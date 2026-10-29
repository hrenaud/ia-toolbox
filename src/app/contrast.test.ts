import { describe, expect, it } from "vitest";

/**
 * WCAG 2.1 relative luminance formula.
 * Computes the relative luminance of a color for contrast calculations.
 */
function getRelativeLuminance(hex: string): number {
  const hex_clean = hex.replace(/^#/, "");
  const r = parseInt(hex_clean.substring(0, 2), 16) / 255;
  const g = parseInt(hex_clean.substring(2, 4), 16) / 255;
  const b = parseInt(hex_clean.substring(4, 6), 16) / 255;

  const rs = r <= 0.03928 ? r / 12.92 : Math.pow((r + 0.055) / 1.055, 2.4);
  const gs = g <= 0.03928 ? g / 12.92 : Math.pow((g + 0.055) / 1.055, 2.4);
  const bs = b <= 0.03928 ? b / 12.92 : Math.pow((b + 0.055) / 1.055, 2.4);

  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Compute contrast ratio between two colors.
 * WCAG 2.1: (Lmax + 0.05) / (Lmin + 0.05)
 */
function getContrastRatio(foreground: string, background: string): number {
  const lFg = getRelativeLuminance(foreground);
  const lBg = getRelativeLuminance(background);

  const lMax = Math.max(lFg, lBg);
  const lMin = Math.min(lFg, lBg);

  return (lMax + 0.05) / (lMin + 0.05);
}

describe("WCAG contrast ratios", () => {
  // Text pairs: require 4.5:1 for normal text (non-large)
  it("warning text #bf360c on #fff3e0 has sufficient contrast", () => {
    const ratio = getContrastRatio("#bf360c", "#fff3e0");
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("info text #1565c0 on #e3f2fd has sufficient contrast", () => {
    const ratio = getContrastRatio("#1565c0", "#e3f2fd");
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("success text #2e7d32 on #e8f5e9 has sufficient contrast", () => {
    const ratio = getContrastRatio("#2e7d32", "#e8f5e9");
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("error text #c62828 on #ffebee has sufficient contrast", () => {
    const ratio = getContrastRatio("#c62828", "#ffebee");
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  // Border pairs on background: require 3:1 for UI component boundaries
  it("border #7c8c9b on background #f4f6f8 has sufficient contrast", () => {
    const ratio = getContrastRatio("#7c8c9b", "#f4f6f8");
    expect(ratio).toBeGreaterThanOrEqual(3);
  });

  it("border #7c8c9b on surface #ffffff has sufficient contrast", () => {
    const ratio = getContrastRatio("#7c8c9b", "#ffffff");
    expect(ratio).toBeGreaterThanOrEqual(3);
  });

  // Dark theme border: already passes
  it("dark theme border #7a8c9c on #141c24 has sufficient contrast", () => {
    const ratio = getContrastRatio("#7a8c9c", "#141c24");
    expect(ratio).toBeGreaterThanOrEqual(3);
  });
});
