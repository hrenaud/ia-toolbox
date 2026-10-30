import type { en } from "../../app/locales/en";
import type { ConversionJob } from "./conversionApi";

/**
 * The error codes the Python worker can report for a single file.
 * Each one needs a `conversion.failure.<code>` string in every locale; adding a
 * code to the worker without one leaves French users reading English.
 */
export const WORKER_ERROR_CODES = [
  "input_not_found",
  "invalid_output_directory",
  "unsupported_format",
  "password_protected",
  "processing_failed",
  "write_failed",
] as const;

type Translations = Record<keyof typeof en, string>;

/**
 * Translate a failed job into a sentence the user can act on.
 *
 * The worker's own message is English only, so it serves as a fallback for a
 * code this build does not know yet rather than as the normal path.
 */
export function describeJobError(job: ConversionJob, t: Translations): string {
  const key = `conversion.failure.${job.errorCode}` as keyof Translations;
  return t[key] ?? job.message ?? t["conversion.unknownError"];
}
