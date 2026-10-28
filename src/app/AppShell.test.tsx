import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

let media: EventTarget & { matches: boolean };
beforeEach(() => {
  vi.spyOn(navigator, "language", "get").mockReturnValue("en-US");
  media = Object.assign(new EventTarget(), { matches: false });
  vi.stubGlobal("matchMedia", () => media);
});

it("renders named navigation and selected workflow content", async () => {
  const user = userEvent.setup();
  render(<AppShell />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Convert to Markdown" }),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Anonymize documents" }));
  expect(
    screen.getByRole("heading", { level: 1, name: "Anonymize documents" }),
  ).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("not available");
});

it("opens a labelled settings dialog, closes on Escape and returns focus", async () => {
  const user = userEvent.setup();
  render(<AppShell />);
  const trigger = screen.getByRole("button", { name: "Settings" });
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Settings" });
  expect(screen.getByLabelText("Language")).toHaveFocus();
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("changes language and appearance, preserving explicit choices on remount", async () => {
  const user = userEvent.setup();
  const view = render(<AppShell />);
  await user.click(screen.getByRole("button", { name: "Settings" }));
  await user.selectOptions(screen.getByLabelText("Language"), "fr");
  expect(document.documentElement.lang).toBe("fr");
  await user.selectOptions(screen.getByLabelText("Apparence"), "dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  view.unmount();
  render(<AppShell />);
  expect(screen.getByRole("button", { name: "Paramètres" })).toBeVisible();
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("follows system language and theme changes without persisting them", () => {
  render(<AppShell />);
  vi.spyOn(navigator, "language", "get").mockReturnValue("fr-FR");
  act(() => window.dispatchEvent(new Event("languagechange")));
  expect(document.documentElement.lang).toBe("fr");
  act(() => {
    media.matches = true;
    media.dispatchEvent(new Event("change"));
  });
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.length).toBe(0);
});
