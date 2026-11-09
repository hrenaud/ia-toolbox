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
  columnPreview,
  describeAnonymizationError,
  detectionKey,
  groupByValue,
  isSelectable,
  showsConfidence,
  valueKey,
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
    likely: true,
    excerpt: "…dossier de Jean Dupont est transféré…",
    column: false,
    ...fields,
  };
}

/** One cell of a column the worker typed as a whole. */
function cell(text: string, start: number): Detection {
  return detection({
    unit_id: "column-0",
    start,
    end: start + text.length,
    text,
    excerpt: text,
    score: 1,
    column: true,
  });
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

  /**
   * Every type the model guesses at scores exactly 0.85, so "high confidence"
   * was printed on every name, organization and place — the three types the
   * user has to check by hand. A word that is always the same word says
   * nothing, and here it was saying the opposite of the truth.
   */
  it.each(["PERSON", "ORGANIZATION", "LOCATION", "DATE_TIME"])(
    "says nothing about confidence for %s, which the model only guesses",
    (type) => {
      expect(showsConfidence(type)).toBe(false);
    },
  );

  it.each(["EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE", "CREDIT_CARD"])(
    "still reports confidence for %s, which a pattern decides",
    (type) => {
      expect(showsConfidence(type)).toBe(true);
    },
  );
});

describe("grouping", () => {
  /**
   * One value is one row, whatever the models made of it. Two models reading
   * one document returned "Claire Dubois" as a person and as an organization,
   * and the screen asked about her twice, under two headings, both times
   * claiming to be sure. The row carries a proposal the user can correct.
   */
  it("asks once about a value the models typed two ways", () => {
    const rows = groupByValue([
      detection({ text: "Claire Dubois", start: 0, end: 13 }),
      detection({
        text: "Claire Dubois",
        start: 40,
        end: 53,
        entity_type: "ORGANIZATION",
      }),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].entityType).toBe("PERSON");
    expect(rows[0].detections).toHaveLength(2);
  });

  it("gives one value one key, whatever type was guessed", () => {
    expect(valueKey(detection({ entity_type: "ORGANIZATION" }))).toBe(
      valueKey(detection({ entity_type: "PERSON" })),
    );
  });

  /** The value alone is often unanswerable; the words around it are not. */
  it("shows the first occurrence in its context", () => {
    const rows = groupByValue([
      detection({ text: "Loire", excerpt: "…salle Loire à 14 heures…" }),
      detection({ text: "Loire", start: 40, end: 45, excerpt: "…la Loire…" }),
    ]);

    expect(rows[0].excerpt).toBe("…salle Loire à 14 heures…");
  });

  it("keeps the worker's type order between rows", () => {
    const rows = groupByValue([
      detection({ text: "a@b.fr", entity_type: "EMAIL_ADDRESS" }),
      detection({ text: "Jean", start: 20, end: 24 }),
    ]);

    expect(rows.map((row) => row.text)).toEqual(["Jean", "a@b.fr"]);
  });

  it("keeps a type the worker added and this build does not know", () => {
    const rows = groupByValue([detection({ entity_type: "FUTURE_TYPE" })]);

    expect(rows[0].entityType).toBe("FUTURE_TYPE");
  });

  /**
   * The same name found eight times is one decision, not eight. Every
   * occurrence of a value already gets the same pseudonym, so asking about
   * each one asks the same question again, and a ten-line document was
   * producing fifty rows.
   */
  it("collapses every occurrence of a value into one row", () => {
    const rows = groupByValue([
      detection({ text: "Claire Dubois", start: 0, end: 13 }),
      detection({ text: "Marc Lefèvre", start: 20, end: 32 }),
      detection({ text: "Claire Dubois", start: 40, end: 53 }),
    ]);

    expect(rows.map((row) => row.text)).toEqual([
      "Claire Dubois",
      "Marc Lefèvre",
    ]);
    expect(rows[0].detections).toHaveLength(2);
  });

  it("collapses two spellings of one value, as the pseudonyms do", () => {
    const rows = groupByValue([
      detection({ text: "Nantes", start: 0, end: 6 }),
      detection({ text: "NANTES", start: 10, end: 16 }),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].text).toBe("Nantes");
  });

  it("ranks the less likely values below the rest", () => {
    const rows = groupByValue([
      detection({ text: "Participants", start: 0, end: 12, likely: false }),
      detection({ text: "Claire Dubois", start: 20, end: 33 }),
    ]);

    expect(rows.map((row) => row.text)).toEqual([
      "Claire Dubois",
      "Participants",
    ]);
    expect(rows.map((row) => row.likely)).toEqual([true, false]);
  });

  it("keeps a value found once in a good place and once in a bad one", () => {
    const rows = groupByValue([
      detection({ text: "Nantes", start: 0, end: 6, likely: false }),
      detection({ text: "Nantes", start: 20, end: 26, likely: true }),
    ]);

    expect(rows[0].likely).toBe(true);
    expect(rows[0].detections).toHaveLength(2);
  });

  it("gives every detection in a unit its own key", () => {
    const first = detectionKey(detection({ start: 0, end: 4 }));
    const second = detectionKey(detection({ start: 6, end: 10 }));

    expect(first).not.toBe(second);
  });
});

/**
 * A column of a table is one decision, not one per cell: every cell in it
 * holds the same kind of value, which is why the worker types the column as a
 * whole. Eight names in a column were eight rows asking the same question, and
 * the one the model missed was not among them at all.
 */
describe("a column is one row", () => {
  it("collapses every cell of a column into a single row", () => {
    const rows = groupByValue([
      cell("Claire Dubois", 0),
      cell("Marc Lefèvre", 14),
      cell("Sophie Marchand", 27),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].column).toBe(true);
    expect(rows[0].detections).toHaveLength(3);
  });

  it("keys a column by its column, so one choice retypes all of it", () => {
    expect(valueKey(cell("Claire Dubois", 0))).toBe(
      valueKey(cell("Marc Lefèvre", 14)),
    );
  });

  /** The same name in prose is still its own question, in its own place. */
  it("keeps a name found in prose out of the column's row", () => {
    const rows = groupByValue([
      cell("Claire Dubois", 0),
      detection({ text: "Claire Dubois", start: 0, end: 13 }),
    ]);

    expect(rows).toHaveLength(2);
  });

  it("previews the first values so the user can judge the type", () => {
    const row = groupByValue([
      cell("Claire Dubois", 0),
      cell("Marc Lefèvre", 14),
    ])[0];

    expect(columnPreview(row)).toBe("Claire Dubois, Marc Lefèvre");
  });

  /** The row has to stay readable: a column can hold thousands of cells. */
  it("stops the preview after a few values and says there are more", () => {
    const row = groupByValue(
      ["Un", "Deux", "Trois", "Quatre", "Cinq", "Six"].map((text, index) =>
        cell(text, index * 10),
      ),
    )[0];

    expect(columnPreview(row)).toBe("Un, Deux, Trois, Quatre…");
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
