import type { en } from "../../app/locales/en";

type Translations = Record<keyof typeof en, string>;

/**
 * The location codes the worker emits, mirroring the list in
 * `python/src/document_worker/anonymization/locations.py`.
 *
 * Each one needs an `anonymization.location.<code>` string in every locale.
 * A code the worker emits and this list does not know reaches the user as a
 * bare identifier, which is what `locationLabels.test.ts` guards against.
 */
export const LOCATION_CODES = [
  "document",
  "column",
  "column_number",
  "line",
  "document_body",
  "header",
  "footer",
  "footnotes",
  "endnotes",
  "comments",
  "slide",
  "slide_notes",
  "slide_layout",
  "slide_master",
  "notes_master",
  "slide_comments",
  "cell_values",
  "sheet",
  "cell_comments",
  "sheet_formulas",
  "sheet_names",
] as const;

/**
 * Turn a worker location into a sentence: "slide:7" becomes "Diapositive 7".
 *
 * The code is everything before the first colon and the detail is everything
 * after it, so a column named "ville: livraison" keeps its own colon. An
 * unknown code is shown as it came rather than hidden: a user can report a
 * string they can see.
 */
export function describeLocation(location: string, t: Translations): string {
  const colon = location.indexOf(":");
  const code = colon === -1 ? location : location.slice(0, colon);
  const detail = colon === -1 ? "" : location.slice(colon + 1);
  const template = t[`anonymization.location.${code}` as keyof Translations];
  if (!template) return location;
  return template.replace("{detail}", detail).trim();
}
