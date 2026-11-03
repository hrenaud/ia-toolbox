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

export interface EntityGroup {
  entityType: string;
  detections: Detection[];
}

/** One value, and every place it was found. */
export interface ValueRow {
  /** The first spelling seen, which is what the row shows. */
  text: string;
  detections: Detection[];
  likely: boolean;
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
 * Group detections by type, in the worker's order, unknown types last.
 *
 * Grouping is what makes bulk selection meaningful — "every email address" is
 * a decision a user can make, "detection 14" is not.
 */
export function groupByEntity(detections: Detection[]): EntityGroup[] {
  const groups = new Map<string, Detection[]>();
  for (const detection of detections) {
    const found = groups.get(detection.entity_type);
    if (found) found.push(detection);
    else groups.set(detection.entity_type, [detection]);
  }
  const rank = (type: string) => {
    const index = ENTITY_TYPES.indexOf(type as (typeof ENTITY_TYPES)[number]);
    return index === -1 ? ENTITY_TYPES.length : index;
  };
  return [...groups.entries()]
    .map(([entityType, found]) => ({ entityType, detections: found }))
    .sort((a, b) => rank(a.entityType) - rank(b.entityType));
}

/**
 * Collapse every occurrence of a value into one row, least likely last.
 *
 * The same name found eight times is one decision, not eight: each occurrence
 * already gets the same pseudonym, so asking about each one asks the same
 * question again. Two spellings of one value are one row for the same reason —
 * the worker assigns its labels case-insensitively, so showing them apart
 * would promise a distinction the output does not make.
 *
 * A value is ranked low only when every occurrence of it is: found once in the
 * middle of a sentence, it is a real value that also happens to open a line
 * somewhere else.
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
        detections: [detection],
        likely: detection.likely,
      });
    }
  }
  return [...rows.values()].sort((a, b) => Number(b.likely) - Number(a.likely));
}

/**
 * The row a detection belongs to: one type, one value, case ignored.
 *
 * The page counts rows with this, so that the count it announces and the rows
 * the user reads are the same thing.
 */
export function valueKey(detection: Detection): string {
  return `${detection.entity_type}|${detection.text.trim().toLocaleLowerCase()}`;
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
