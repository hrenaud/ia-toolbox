import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { en } from "../../app/locales/en";
import { fr } from "../../app/locales/fr";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";
import {
  ENTITY_TYPES,
  NOTE_CODES,
  PIPELINE_ERROR_CODES,
  anonymizedName,
  confidenceWord,
  describeAnonymizationError,
  detectionKey,
  groupByEntity,
  isSelectable,
} from "./review";

/**
 * The review screen is where the user decides, so everything it says has to be
 * translated and nothing it offers may be something the format cannot rewrite.
 * The vocabulary lists here are checked against the worker's own, and against
 * both locales.
 */

function detection(fields: Partial<Detection> = {}): Detection {
  return {
    unit_id: "word/document.xml|text",
    start: 0,
    end: 11,
    entity_type: "PERSON",
    score: 0.85,
    text: "Jean Dupont",
    ...fields,
  };
}

function unit(fields: Partial<AnalyzedUnit> = {}): AnalyzedUnit {
  return {
    id: "word/document.xml|text",
    location: "document_body",
    rewritable: true,
    ...fields,
  };
}

describe("the entity list mirrors the worker's", () => {
  it("declares exactly the types the worker can report", () => {
    const source = readFileSync(
      resolve(
        process.cwd(),
        "python/src/document_worker/anonymization/detection.py",
      ),
      "utf8",
    );
    const block = source.slice(
      source.indexOf("ENTITY_TYPES = ("),
      source.indexOf(")", source.indexOf("ENTITY_TYPES = (")),
    );
    const declared = [...block.matchAll(/"([A-Z_]+)"/g)].map(
      (match) => match[1],
    );

    expect(declared).not.toHaveLength(0);
    expect([...ENTITY_TYPES].sort()).toEqual(declared.sort());
  });

  it.each(ENTITY_TYPES)("translates %s in both languages", (type) => {
    expect(en).toHaveProperty(`anonymization.entity.${type}`);
    expect(fr).toHaveProperty(`anonymization.entity.${type}`);
  });
});

describe("confidence is a word, never a shade", () => {
  it.each([
    [1, "high"],
    [0.85, "high"],
    [0.7, "medium"],
    [0.4, "low"],
    [0, "low"],
  ])("reads %s as %s", (score, word) => {
    expect(confidenceWord(score)).toBe(word);
  });

  it.each(["high", "medium", "low"])("translates %s", (word) => {
    expect(en).toHaveProperty(`anonymization.confidence.${word}`);
    expect(fr).toHaveProperty(`anonymization.confidence.${word}`);
  });
});

describe("grouping", () => {
  it("groups by entity type and keeps the worker's order", () => {
    const groups = groupByEntity([
      detection({ entity_type: "EMAIL_ADDRESS", text: "a@b.fr" }),
      detection({ entity_type: "PERSON", text: "Jean" }),
      detection({ entity_type: "PERSON", text: "Marie" }),
    ]);

    expect(groups.map((group) => group.entityType)).toEqual([
      "PERSON",
      "EMAIL_ADDRESS",
    ]);
    expect(groups[0].detections).toHaveLength(2);
  });

  it("keeps a type the worker added and this build does not know", () => {
    const groups = groupByEntity([detection({ entity_type: "FUTURE_TYPE" })]);

    expect(groups.map((group) => group.entityType)).toEqual(["FUTURE_TYPE"]);
  });

  it("gives every detection in a unit its own key", () => {
    const first = detectionKey(detection({ start: 0, end: 4 }));
    const second = detectionKey(detection({ start: 6, end: 10 }));

    expect(first).not.toBe(second);
  });
});

describe("what may be selected", () => {
  const units = [
    unit(),
    unit({ id: "xl/worksheets/sheet1.xml|formula", rewritable: false }),
  ];

  it("offers text the format can rewrite", () => {
    expect(isSelectable(detection(), units)).toBe(true);
  });

  it("never offers text the format cannot rewrite", () => {
    const frozen = detection({ unit_id: "xl/worksheets/sheet1.xml|formula" });

    expect(isSelectable(frozen, units)).toBe(false);
  });

  it("refuses a detection whose unit is not in the analysis", () => {
    expect(isSelectable(detection({ unit_id: "gone" }), units)).toBe(false);
  });
});

describe("failures and notes", () => {
  it.each(PIPELINE_ERROR_CODES)("translates %s in both languages", (code) => {
    expect(en).toHaveProperty(`anonymization.failure.${code}`);
    expect(fr).toHaveProperty(`anonymization.failure.${code}`);
    expect(describeAnonymizationError(code, undefined, fr)).not.toBe(
      describeAnonymizationError(code, undefined, en),
    );
  });

  it.each(NOTE_CODES)("translates the note %s in both languages", (code) => {
    expect(en).toHaveProperty(`anonymization.note.${code}`);
    expect(fr).toHaveProperty(`anonymization.note.${code}`);
  });

  it("tells the user to analyze again when the document changed", () => {
    expect(
      describeAnonymizationError("document_changed", undefined, fr),
    ).toContain("nouveau");
  });

  it("falls back to the worker message for a code this build does not know", () => {
    expect(describeAnonymizationError("future_code", "Raw detail", fr)).toBe(
      "Raw detail",
    );
  });

  it("uses the generic wording when the failure carries nothing", () => {
    expect(describeAnonymizationError(undefined, undefined, fr)).toBe(
      fr["anonymization.unknownError"],
    );
  });
});

/**
 * The name shown before the user confirms has to match the name the worker
 * writes, suffix included, or the confirmation names a file that never
 * appears. The rule is `_output_path` in the worker's `pipeline.py`.
 */
describe("anonymizedName", () => {
  it("suffixes the stem and keeps the extension", () => {
    expect(anonymizedName("/home/u/rapport.docx", "fr")).toBe(
      "rapport-anonymise.docx",
    );
  });

  it("uses the English suffix the worker uses for English", () => {
    expect(anonymizedName("/home/u/report.docx", "en")).toBe(
      "report-anonymized.docx",
    );
  });

  it("reads the name out of a Windows path", () => {
    expect(anonymizedName("C:\\Users\\u\\notes.md", "fr")).toBe(
      "notes-anonymise.md",
    );
  });

  it("keeps only the last extension of a dotted name", () => {
    expect(anonymizedName("/tmp/notes.2026-01.csv", "fr")).toBe(
      "notes.2026-01-anonymise.csv",
    );
  });

  it("suffixes a name that has no extension at all", () => {
    expect(anonymizedName("/tmp/LISEZMOI", "fr")).toBe("LISEZMOI-anonymise");
  });

  it("matches the suffixes the worker declares", () => {
    const source = readFileSync(
      resolve(
        process.cwd(),
        "python/src/document_worker/anonymization/pipeline.py",
      ),
      "utf8",
    );
    expect(source).toContain(
      '_SUFFIXES = {"fr": "-anonymise", "en": "-anonymized"}',
    );
  });
});
