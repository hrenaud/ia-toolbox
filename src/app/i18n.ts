import { en } from "./locales/en";
import { fr } from "./locales/fr";

export type Locale = "en" | "fr";
export const dictionaries = { en, fr };

export function getInitialLocale(
  systemLocale: string,
  savedLocale: Locale | null,
): Locale {
  return (
    savedLocale ??
    (systemLocale.toLowerCase().split("-")[0] === "fr" ? "fr" : "en")
  );
}
