import type { en } from "../../app/locales/en";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";

type Translations = Record<keyof typeof en, string>;

/**
 * The entity types the worker can report, mirroring `ENTITY_TYPES` in
 * `python/src/document_worker/anonymization/detection.py`. The order is the
 * order the review screen groups them in.
 */
export const ENTITY_TYPES = [
  "PERSON",
  "ORGANIZATION",
  "LOCATION",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "IBAN_CODE",
  "CREDIT_CARD",
  "FR_NIR",
  "DATE_TIME",
] as const;

/**
 * The types a language model guesses at, mirroring `_MODEL_TYPES` in the
 * worker's `detection.py`. Everything else is decided by a pattern, often by a
 * check digit, which is what makes its score worth reporting.
 */
export const MODEL_TYPES = [
  "PERSON",
  "ORGANIZATION",
  "LOCATION",
  "DATE_TIME",
] as const;

/** The languages the worker has a model for, mirroring its `LANGUAGES`. */
export const DOCUMENT_LANGUAGES = ["fr", "en"] as const;

/** Failures the anonymization pipeline reports, keyed for translation. */
export const PIPELINE_ERROR_CODES = [
  "input_not_found",
  "unsupported_format",
  "password_protected",
  "invalid_output_directory",
  "document_changed",
  "not_rewritable",
  "invalid_request",
  "write_failed",
] as const;

/** What the adapters read but do not rewrite, and tell the user about. */
export const NOTE_CODES = [
  "markup_code_not_analyzed",
  "xml_attributes_not_analyzed",
  "tracked_changes_not_rewritten",
  "document_properties_not_rewritten",
  "xlsx_shared_strings_reused",
] as const;

/** One value, every place it was found, and the type proposed for it. */
export interface ValueRow {
  /** The first spelling seen, which is what the row shows. */
  text: string;
  /**
   * The type the worker proposed, which the user may override. It comes from
   * the first occurrence: two models disagreeing about one value is exactly
   * what the override exists for.
   */
  entityType: string;
  /** The first occurrence in its context, as the worker cut it. */
  excerpt: string;
  detections: Detection[];
  likely: boolean;
  /**
   * True when the row is a whole column of a table rather than one value. The
   * row then holds one detection per cell, all of one type, and the screen
   * names the column instead of naming the first of its values.
   */
  column: boolean;
}

/** How many of a column's values the row shows before it gets unreadable. */
const PREVIEW_CELLS = 4;

/**
 * The first few values of a column, so the user can judge the type.
 *
 * This is what makes a whole-column decision answerable: the row says "this
 * column is names" and the preview is the evidence, including the cell the
 * model missed — which is the one the user could never see before.
 */
export function columnPreview(row: ValueRow): string {
  const values = row.detections.map((detection) => detection.text);
  const shown = values.slice(0, PREVIEW_CELLS).join(", ");
  return values.length > PREVIEW_CELLS ? `${shown}…` : shown;
}

/** Identify one detection within one analysis, for selection state. */
export function detectionKey(detection: Detection): string {
  return `${detection.unit_id}|${detection.start}-${detection.end}`;
}

/**
 * Say how sure the detector is in words.
 *
 * A colour or a bar would be the obvious design and the wrong one: it is the
 * only cue, so it has to survive a screen reader and a monochrome display.
 * The thresholds follow the detector: a pattern with a verified check digit
 * scores 1, a model-tagged name around 0.85, a bare pattern much lower.
 */
export function confidenceWord(score: number): "high" | "medium" | "low" {
  if (score >= 0.85) return "high";
  if (score >= 0.6) return "medium";
  return "low";
}

/**
 * Whether a score is worth showing at all for this type.
 *
 * Every type the model guesses at scores exactly 0.85, so "high confidence"
 * was printed on every name, organization and place — the three types the user
 * has to check one by one. A word that never changes is not information, and
 * here it contradicted what the user was seeing. For the types a pattern
 * decides, the score still varies and still means something: a verified check
 * digit scores 1, a bare run of digits that looks like a phone number scores
 * much lower.
 */
export function showsConfidence(entityType: string): boolean {
  return !MODEL_TYPES.includes(entityType as (typeof MODEL_TYPES)[number]);
}

/**
 * Collapse every occurrence of a value into one row, least likely last.
 *
 * The same name found eight times is one decision, not eight: each occurrence
 * already gets the same pseudonym, so asking about each one asks the same
 * question again, and a ten-line document was producing fifty rows. Two
 * spellings of one value are one row for the same reason — the worker assigns
 * its labels case-insensitively.
 *
 * The type is not part of the key either. Two models reading one document
 * returned "Claire Dubois" as a person and as an organization, and the screen
 * asked about her twice, under two headings, both times claiming to be sure.
 * One value is one question; the type is a proposal the user can correct.
 *
 * A column of a table is one row for a stronger reason: the worker typed the
 * column as a whole, so the row holds every one of its cells and the user's
 * answer covers all of them at once.
 *
 * A value is ranked low only when every occurrence of it is: found once in the
 * middle of a sentence, it is a real value that also happens to open a line
 * somewhere else. Below that, rows keep the worker's type order, so the rows
 * that ask the same kind of question sit together.
 */
export function groupByValue(detections: Detection[]): ValueRow[] {
  const rows = new Map<string, ValueRow>();
  for (const detection of detections) {
    const key = valueKey(detection);
    const found = rows.get(key);
    if (found) {
      found.detections.push(detection);
      found.likely ||= detection.likely;
    } else {
      rows.set(key, {
        text: detection.text,
        entityType: detection.entity_type,
        excerpt: detection.excerpt,
        detections: [detection],
        likely: detection.likely,
        column: detection.column,
      });
    }
  }
  return [...rows.values()].sort(
    (a, b) =>
      Number(b.likely) - Number(a.likely) ||
      typeRank(a.entityType) - typeRank(b.entityType),
  );
}

/**
 * The row a detection belongs to: one value, case ignored, type ignored.
 *
 * The page counts rows with this and holds the user's type choices under it,
 * so the count it announces, the rows the user reads and the type they pick are
 * all the same thing.
 *
 * A cell of a typed column is keyed by its column instead. Every cell in a
 * column holds the same kind of value, so the question is about the column:
 * eight names were eight identical rows, and one choice now retypes all of
 * them — including the cell the model missed, which no row ever offered.
 */
export function valueKey(detection: Detection): string {
  if (detection.column) return `column:${detection.unit_id}`;
  return detection.text.trim().toLocaleLowerCase();
}

/** Where a type sits in the worker's order; a type we do not know goes last. */
function typeRank(entityType: string): number {
  const index = ENTITY_TYPES.indexOf(
    entityType as (typeof ENTITY_TYPES)[number],
  );
  return index === -1 ? ENTITY_TYPES.length : index;
}

/**
 * Whether this detection may be offered for replacement.
 *
 * A formula literal or a sheet name is read and shown so nothing is hidden,
 * but rewriting it by offset is how a workbook stops opening. Keeping it out
 * of the selection here is what stops the worker answering `not_rewritable`.
 */
export function isSelectable(
  detection: Detection,
  units: AnalyzedUnit[],
): boolean {
  const unit = units.find((candidate) => candidate.id === detection.unit_id);
  return unit?.rewritable ?? false;
}

/**
 * The name the worker will give the copy, so the confirmation can name it.
 *
 * It mirrors `_output_path` in the worker's `pipeline.py`, suffix included.
 * The numbered suffix a collision adds is deliberately not guessed here: only
 * the worker can see the output folder, so the confirmation names the file it
 * will try to write and the result reports the path it actually wrote.
 */
export function anonymizedName(inputPath: string, language: string): string {
  const basename = inputPath.split(/[\\/]/).pop() ?? inputPath;
  const suffix = language === "en" ? "-anonymized" : "-anonymise";
  const dot = basename.lastIndexOf(".");
  if (dot <= 0) return `${basename}${suffix}`;
  return `${basename.slice(0, dot)}${suffix}${basename.slice(dot)}`;
}

/**
 * Translate a failure into a sentence the user can act on.
 *
 * The worker's own message is English only, so it is the fallback for a code
 * this build does not know yet rather than the normal path.
 */
export function describeAnonymizationError(
  code: string | undefined,
  message: string | undefined,
  t: Translations,
): string {
  const key = `anonymization.failure.${code}` as keyof Translations;
  return t[key] ?? message ?? t["anonymization.unknownError"];
}
