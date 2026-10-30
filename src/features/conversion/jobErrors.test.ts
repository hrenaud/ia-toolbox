import { describe, expect, it } from "vitest";

import { en } from "../../app/locales/en";
import { fr } from "../../app/locales/fr";
import { WORKER_ERROR_CODES, describeJobError } from "./jobErrors";
import type { ConversionJob } from "./conversionApi";

/**
 * The worker writes its messages in English only, and the UI used to render
 * them verbatim, so a French user got an English sentence on every failure.
 * These cases pin the translation of each code the worker can emit.
 */

function failedJob(fields: Partial<ConversionJob>): ConversionJob {
  return {
    id: "job-1",
    inputPath: "/documents/rapport.pdf",
    status: "error",
    ...fields,
  };
}

describe("describeJobError", () => {
  it.each(WORKER_ERROR_CODES)("translates %s in both languages", (code) => {
    const job = failedJob({ errorCode: code, message: "English fallback" });

    expect(describeJobError(job, en)).not.toBe("English fallback");
    expect(describeJobError(job, fr)).not.toBe(describeJobError(job, en));
  });

  it("explains a password-protected file instead of blaming file access", () => {
    const job = failedJob({ errorCode: "password_protected" });

    expect(describeJobError(job, fr)).toContain("mot de passe");
    expect(describeJobError(job, en)).toContain("password");
  });

  it("falls back to the worker message for an unknown code", () => {
    const job = failedJob({ errorCode: "future_code", message: "Raw detail" });

    expect(describeJobError(job, fr)).toBe("Raw detail");
  });

  it("falls back to the worker message when no code is reported", () => {
    const job = failedJob({ message: "Conversion failed: spawn error" });

    expect(describeJobError(job, fr)).toBe("Conversion failed: spawn error");
  });

  it("uses the generic wording when the failure carries nothing at all", () => {
    expect(describeJobError(failedJob({}), fr)).toBe(
      fr["conversion.unknownError"],
    );
  });
});

describe("worker error catalog", () => {
  it("declares a translation for every code in both locales", () => {
    for (const code of WORKER_ERROR_CODES) {
      expect(en).toHaveProperty(`conversion.failure.${code}`);
      expect(fr).toHaveProperty(`conversion.failure.${code}`);
    }
  });
});
