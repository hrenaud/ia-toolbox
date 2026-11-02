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
