import { describe, expect, it } from "vitest";
import {
  formatListForDisplay,
  isSupportedFormat,
  requiresOptionalComponent,
} from "./formatLabels";
import type { FormatInfo } from "./conversionApi";

/**
 * The worker's catalog (python/src/document_worker/formats.py) declares
 * extensions with a leading dot. An earlier version of this module compared
 * them against undotted extensions, so nothing was ever recognised as
 * convertible and the Convert button stayed disabled forever. These cases pin
 * the dotted convention on both sides of the comparison.
 */
const catalog: FormatInfo[] = [
  { extension: ".pdf", label: "PDF", requiresOptionalComponent: false },
  {
    extension: ".docx",
    label: "Word Document",
    requiresOptionalComponent: false,
  },
  {
    extension: ".markdown",
    label: "Markdown",
    requiresOptionalComponent: false,
  },
  { extension: ".tiff", label: "TIFF", requiresOptionalComponent: true },
];

describe("isSupportedFormat", () => {
  it("accepts a file whose dotted extension is in the catalog", () => {
    expect(isSupportedFormat("report.pdf", catalog)).toBe(true);
    expect(isSupportedFormat("notes.markdown", catalog)).toBe(true);
  });

  it("ignores case in both the filename and the catalog", () => {
    expect(isSupportedFormat("REPORT.PDF", catalog)).toBe(true);
  });

  it("matches the last extension of a multi-dotted filename", () => {
    expect(isSupportedFormat("archive.tar.docx", catalog)).toBe(true);
    expect(isSupportedFormat("report.docx.xyz", catalog)).toBe(false);
  });

  it("rejects an unknown extension", () => {
    expect(isSupportedFormat("mystery.xyz", catalog)).toBe(false);
  });

  it("rejects a file with no extension, including a dotfile", () => {
    expect(isSupportedFormat("README", catalog)).toBe(false);
    expect(isSupportedFormat(".pdf", catalog)).toBe(false);
  });

  it("rejects a known format that needs an optional component", () => {
    expect(isSupportedFormat("scan.tiff", catalog)).toBe(false);
  });

  it("rejects everything when the catalog has not loaded", () => {
    expect(isSupportedFormat("report.pdf", [])).toBe(false);
  });
});

describe("requiresOptionalComponent", () => {
  it("reports a known format gated behind an optional component", () => {
    expect(requiresOptionalComponent("scan.tiff", catalog)).toBe(true);
  });

  it("does not report convertible or unknown formats", () => {
    expect(requiresOptionalComponent("report.pdf", catalog)).toBe(false);
    expect(requiresOptionalComponent("mystery.xyz", catalog)).toBe(false);
  });
});

describe("formatListForDisplay", () => {
  it("lists the catalog labels in order", () => {
    expect(formatListForDisplay(catalog)).toBe(
      "PDF, Word Document, Markdown, TIFF",
    );
  });

  it("returns an empty string for an empty catalog", () => {
    expect(formatListForDisplay([])).toBe("");
  });
});
