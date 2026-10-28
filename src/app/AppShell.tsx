import { useEffect, useRef, useState } from "react";
import { ConversionPage } from "../features/conversion/ConversionPage";
import { dictionaries, getInitialLocale, type Locale } from "./i18n";
import { loadSettings, saveSettings, type Settings } from "./settings";
import { getTheme, type ThemePreference } from "./theme";

export function AppShell() {
  const [settings, setSettings] = useState(loadSettings);
  const [systemLocale, setSystemLocale] = useState(() => navigator.language);
  const [systemIsDark, setSystemIsDark] = useState(
    () => matchMedia("(prefers-color-scheme: dark)").matches,
  );
  const [workflow, setWorkflow] = useState<"convert" | "anonymize">("convert");
  const dialog = useRef<HTMLDialogElement>(null);
  const settingsButton = useRef<HTMLButtonElement>(null);
  const locale = getInitialLocale(systemLocale, settings.locale);
  const t = dictionaries[locale];

  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const updateTheme = () => setSystemIsDark(media.matches);
    const updateLocale = () => setSystemLocale(navigator.language);
    media.addEventListener("change", updateTheme);
    window.addEventListener("languagechange", updateLocale);
    // Refresh on returning from OS settings, including WebViews that defer events.
    window.addEventListener("focus", updateLocale);
    window.addEventListener("focus", updateTheme);
    return () => {
      media.removeEventListener("change", updateTheme);
      window.removeEventListener("languagechange", updateLocale);
      window.removeEventListener("focus", updateLocale);
      window.removeEventListener("focus", updateTheme);
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = t.appName;
    document.documentElement.dataset.theme = getTheme(
      settings.theme,
      systemIsDark,
    );
  }, [locale, t.appName, settings.theme, systemIsDark]);

  function changeSettings(next: Settings) {
    saveSettings(next);
    setSettings(next);
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        {t.skip}
      </a>
      <header className="app-header">
        <div>
          <p className="brand">{t.appName}</p>
          <p className="muted">{t.tagline}</p>
        </div>
        <button
          ref={settingsButton}
          onClick={() => dialog.current?.showModal()}
          aria-haspopup="dialog"
        >
          {t.settings}
        </button>
      </header>
      <div className="workspace">
        <nav aria-label={t.workflows}>
          <p className="nav-label">{t.workflows}</p>
          {(["convert", "anonymize"] as const).map((item) => (
            <button
              key={item}
              aria-current={workflow === item ? "page" : undefined}
              onClick={() => setWorkflow(item)}
            >
              {t[item]}
            </button>
          ))}
        </nav>
        <main id="main" tabIndex={-1}>
          <p className="eyebrow">{t.local}</p>
          <h1>{t[workflow]}</h1>
          <p className="description">
            {workflow === "convert"
              ? t.convertDescription
              : t.anonymizeDescription}
          </p>
          {workflow === "convert" ? (
            <ConversionPage locale={locale} />
          ) : (
            <div className="status-card" role="status">
              <p>{t.unavailable}</p>
            </div>
          )}
          <p className="privacy">{t.privacy}</p>
        </main>
      </div>
      <dialog
        ref={dialog}
        aria-labelledby="settings-title"
        aria-describedby="settings-description"
        onClose={() => settingsButton.current?.focus()}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            dialog.current?.close();
          }
        }}
      >
        <h2 id="settings-title">{t.settings}</h2>
        <p id="settings-description" className="muted">
          {t.preferences}
        </p>
        <label htmlFor="language">{t.language}</label>
        <select
          id="language"
          value={settings.locale ?? "system"}
          onChange={(event) =>
            changeSettings({
              ...settings,
              locale:
                event.target.value === "system"
                  ? null
                  : (event.target.value as Locale),
            })
          }
        >
          <option value="system">{t.system}</option>
          <option value="en" lang="en">
            {t.english}
          </option>
          <option value="fr" lang="fr">
            {t.french}
          </option>
        </select>
        <label htmlFor="appearance">{t.appearance}</label>
        <select
          id="appearance"
          value={settings.theme}
          onChange={(event) =>
            changeSettings({
              ...settings,
              theme: event.target.value as ThemePreference,
            })
          }
        >
          <option value="system">{t.system}</option>
          <option value="light">{t.light}</option>
          <option value="dark">{t.dark}</option>
        </select>
        <p className="muted settings-note">{t.saved}</p>
        <button className="primary" onClick={() => dialog.current?.close()}>
          {t.close}
        </button>
      </dialog>
    </div>
  );
}
