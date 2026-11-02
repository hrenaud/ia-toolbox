import { getClient, stopClient } from "../../app/worker/sharedClient";
import type { FormatInfo as WorkerFormatInfo } from "../../app/worker/sidecarClient";

/**
 * UI-facing format information with camelCase names
 */
export interface FormatInfo {
  extension: string;
  label: string;
  requiresOptionalComponent: boolean;
}

/**
 * Conversion job state as seen by the UI
 */
export interface ConversionJob {
  id: string;
  inputPath: string;
  outputPath?: string;
  status: "queued" | "running" | "success" | "error";
  progress?: number;
  /** The worker's error code, used to pick a translated message. */
  errorCode?: string;
  /** The worker's own English message, kept as a fallback for unknown codes. */
  message?: string;
}

/**
 * Load the list of supported formats from the worker.
 * Maps worker's snake_case fields to UI's camelCase.
 */
export async function loadSupportedFormats(): Promise<FormatInfo[]> {
  try {
    const c = await getClient();
    const result = await c.request({ operation: "list_formats" });
    if (result.event !== "formats") {
      throw new Error("unexpected_response");
    }
    return result.items.map((item: WorkerFormatInfo) => ({
      extension: item.extension,
      label: item.label,
      // Only the anonymization catalog omits the flag; conversion always sends it.
      requiresOptionalComponent: item.requires_optional_component ?? false,
    }));
  } catch (err) {
    throw mapError(err);
  }
}

/**
 * Start conversion of files to Markdown.
 * Processes files sequentially; calls onUpdate for each job state change and progress.
 * The job state machine tolerates progress events followed by error results.
 */
export async function startConversion(
  inputPaths: string[],
  outputDirectory: string,
  onUpdate: (job: ConversionJob) => void,
): Promise<void> {
  try {
    const c = await getClient();
    for (const inputPath of inputPaths) {
      const id = crypto.randomUUID();
      onUpdate({ id, inputPath, status: "queued" });

      try {
        onUpdate({ id, inputPath, status: "running" });

        const result = await c.request(
          {
            operation: "convert",
            input_path: inputPath,
            output_directory: outputDirectory,
          },
          (percent) => {
            onUpdate({ id, inputPath, status: "running", progress: percent });
          },
        );

        if (result.event === "result") {
          if (result.status === "error") {
            onUpdate({
              id,
              inputPath,
              status: "error",
              errorCode: result.error_code,
              message: result.message,
            });
            // A conversion answers with a written file; the client rejects
            // anything else before it reaches here.
          } else if ("output_path" in result) {
            onUpdate({
              id,
              inputPath,
              outputPath: result.output_path,
              status: "success",
            });
          }
        }
      } catch (err) {
        onUpdate({
          id,
          inputPath,
          status: "error",
          message: `Conversion failed: ${getErrorMessage(err)}`,
        });
      }
    }
  } catch (err) {
    throw mapError(err);
  }
}

/** Stop the sidecar client (cleanup on app shutdown). */
export { stopClient };

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}

function mapError(err: unknown): Error {
  if (err instanceof Error) {
    return err;
  }
  return new Error(String(err));
}
