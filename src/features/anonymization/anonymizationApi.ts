import { getClient } from "../../app/worker/sharedClient";
import {
  WorkerError,
  type AnalyzedUnit,
  type Detection,
  type FormatInfo,
  type KeptDetection,
} from "../../app/worker/sidecarClient";

/** One document, as the page sees it through both phases. */
export interface AnalyzedDocument {
  inputPath: string;
  status: "queued" | "analyzing" | "success" | "error";
  units: AnalyzedUnit[];
  detections: Detection[];
  /** Codes for content that was read but not analyzed, or not rewritten. */
  notes: string[];
  /** Where the anonymized copy went, once there is one. */
  outputPath?: string;
  errorCode?: string;
  /** The worker's English message, a fallback for a code we do not know. */
  message?: string;
}

export interface AnonymizeChoices {
  outputDirectory: string;
  operator: string;
  language: string;
}

/**
 * The formats that can be anonymized.
 *
 * A separate catalog from conversion's on purpose: converting a PDF to
 * Markdown is one thing, rewriting a PDF in place is another, and only the
 * second is what this screen promises.
 */
export async function loadAnonymizationFormats(): Promise<FormatInfo[]> {
  const client = await getClient();
  const result = await client.request({
    operation: "list_anonymization_formats",
  });
  if (result.event !== "formats") throw new WorkerError("invalid_response");
  return result.items;
}

/**
 * Read each document in turn and report what is in it.
 *
 * One unreadable document is not a failed batch — the user picked ten files
 * and nine of them are fine, so each one carries its own error code. The
 * worker going away is different: every remaining document would fail the same
 * way, so that error is raised instead of repeated.
 */
export async function analyzeDocuments(
  inputPaths: string[],
  onUpdate: (document: AnalyzedDocument) => void,
): Promise<void> {
  const client = await getClient();
  for (const inputPath of inputPaths) {
    const empty: AnalyzedDocument = {
      inputPath,
      status: "analyzing",
      units: [],
      detections: [],
      notes: [],
    };
    onUpdate(empty);
    const result = await client.request({
      operation: "analyze",
      input_path: inputPath,
    });
    if (result.event !== "result") throw new WorkerError("invalid_response");
    if (result.status === "error") {
      onUpdate({
        ...empty,
        status: "error",
        errorCode: result.error_code,
        message: result.message,
      });
    } else if ("units" in result) {
      onUpdate({
        ...empty,
        status: "success",
        units: result.units,
        detections: result.detections,
        notes: result.notes,
      });
    }
  }
}

/**
 * Write an anonymized copy of each document, replacing only what was kept.
 *
 * A document with nothing kept is left alone rather than copied unchanged: a
 * file named "-anonymise" that is identical to the original is a claim the
 * user did not make.
 */
export async function anonymizeDocuments(
  documents: { inputPath: string; detections: KeptDetection[] }[],
  choices: AnonymizeChoices,
  onUpdate: (document: AnalyzedDocument) => void,
): Promise<void> {
  const pending = documents.filter((item) => item.detections.length > 0);
  if (pending.length === 0) return;

  const client = await getClient();
  for (const { inputPath, detections } of pending) {
    const empty: AnalyzedDocument = {
      inputPath,
      status: "analyzing",
      units: [],
      detections: [],
      notes: [],
    };
    onUpdate(empty);
    const result = await client.request({
      operation: "anonymize",
      input_path: inputPath,
      output_directory: choices.outputDirectory,
      operator: choices.operator,
      language: choices.language,
      detections,
    });
    if (result.event !== "result") throw new WorkerError("invalid_response");
    if (result.status === "error") {
      onUpdate({
        ...empty,
        status: "error",
        errorCode: result.error_code,
        message: result.message,
      });
    } else if ("output_path" in result) {
      onUpdate({
        ...empty,
        status: "success",
        outputPath: result.output_path,
        notes: result.notes ?? [],
      });
    }
  }
}
