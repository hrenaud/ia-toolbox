import { describe, expect, it } from "vitest";
import { getInitialLocale } from "./i18n";
import { getTheme } from "./theme";
import { loadSettings, saveSettings } from "./settings";

describe("locale selection", () => {
  it.each(["fr", "fr-FR", "fr-CA", "FR-be"])(
    "selects French for %s",
    (locale) => {
      expect(getInitialLocale(locale, null)).toBe("fr");
    },
  );
  it.each(["en", "en-GB", "de-DE", ""])(
    "defaults to English for %s",
    (locale) => {
      expect(getInitialLocale(locale, null)).toBe("en");
    },
  );
  it("honors saved choices over the system locale", () => {
    expect(getInitialLocale("fr-FR", "en")).toBe("en");
    expect(getInitialLocale("en-US", "fr")).toBe("fr");
  });
});

describe("appearance", () => {
  it.each([
    ["system", false, "light"],
    ["system", true, "dark"],
    ["light", false, "light"],
    ["light", true, "light"],
    ["dark", false, "dark"],
    ["dark", true, "dark"],
  ] as const)(
    "resolves %s with system dark=%s",
    (preference, dark, expected) => {
      expect(getTheme(preference, dark)).toBe(expected);
    },
  );
});

describe("local settings", () => {
  it("leaves system defaults unset", () => {
    expect(loadSettings()).toEqual({ locale: null, theme: "system" });
    saveSettings({ locale: null, theme: "system" });
    expect(localStorage.length).toBe(0);
  });
  it("persists explicit choices and removes them when returning to System", () => {
    saveSettings({ locale: "fr", theme: "dark" });
    expect(loadSettings()).toEqual({ locale: "fr", theme: "dark" });
    saveSettings({ locale: null, theme: "system" });
    expect(localStorage.length).toBe(0);
  });
  it("ignores invalid saved values", () => {
    localStorage.setItem("ia-toolbox.locale", "xx");
    localStorage.setItem("ia-toolbox.theme", "sepia");
    expect(loadSettings()).toEqual({ locale: null, theme: "system" });
  });
});
