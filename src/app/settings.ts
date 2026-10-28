import type { Locale } from "./i18n";
import type { ThemePreference } from "./theme";
export interface Settings {
  locale: Locale | null;
  theme: ThemePreference;
}
export function loadSettings(): Settings {
  const locale = localStorage.getItem("ia-toolbox.locale");
  const theme = localStorage.getItem("ia-toolbox.theme");
  return {
    locale: locale === "en" || locale === "fr" ? locale : null,
    theme: theme === "light" || theme === "dark" ? theme : "system",
  };
}
export function saveSettings(settings: Settings): void {
  if (settings.locale === null) localStorage.removeItem("ia-toolbox.locale");
  else localStorage.setItem("ia-toolbox.locale", settings.locale);
  if (settings.theme === "system") localStorage.removeItem("ia-toolbox.theme");
  else localStorage.setItem("ia-toolbox.theme", settings.theme);
}
