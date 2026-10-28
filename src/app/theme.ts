export type ThemePreference = "system" | "light" | "dark";
export function getTheme(
  preference: ThemePreference,
  systemIsDark: boolean,
): "light" | "dark" {
  return preference === "system"
    ? systemIsDark
      ? "dark"
      : "light"
    : preference;
}
