import type { FormatInfo } from "./conversionApi";

/**
 * Check if a file extension is supported for conversion
 */
export function isSupportedFormat(
  filename: string,
  formats: FormatInfo[],
): boolean {
  const extension = getFileExtension(filename).toLowerCase();
  return formats.some(
    (format) =>
      format.extension.toLowerCase() === extension &&
      !format.requiresOptionalComponent,
  );
}

/**
 * Check if a format is recognized but requires an optional component
 */
export function requiresOptionalComponent(
  filename: string,
  formats: FormatInfo[],
): boolean {
  const extension = getFileExtension(filename).toLowerCase();
  return formats.some(
    (format) =>
      format.extension.toLowerCase() === extension &&
      format.requiresOptionalComponent,
  );
}

/**
 * Get the file extension from a filename (lowercase, without dot)
 */
function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf(".");
  return lastDot > 0 ? filename.slice(lastDot + 1) : "";
}

/**
 * Format a list of formats for display (e.g., "PDF, Word, CSV")
 */
export function formatListForDisplay(formats: FormatInfo[]): string {
  return formats.map((f) => f.label).join(", ");
}
