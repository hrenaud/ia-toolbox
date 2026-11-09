import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { en } from "../../app/locales/en";
import { fr } from "../../app/locales/fr";
import { LOCATION_CODES, describeLocation } from "./locationLabels";

/**
 * The worker says where a detection is as a code, and this is where that code
 * becomes a sentence. Two things can go wrong, and both show a user a bare
 * identifier: a code the worker emits and this list does not know, and a code
 * this list knows and a locale does not translate. Both are checked here, the
 * first against the Python file itself.
 */

const PYTHON_CODES = resolve(
  process.cwd(),
  "python/src/document_worker/anonymization/locations.py",
);

describe("the code list mirrors the worker's", () => {
  it("declares exactly the codes the worker can emit", () => {
    const source = readFileSync(PYTHON_CODES, "utf8");
    const declared = [...source.matchAll(/^\s+"([a-z_]+)",$/gm)].map(
      (match) => match[1],
    );

    expect(declared).not.toHaveLength(0);
    expect([...LOCATION_CODES].sort()).toEqual(declared.sort());
  });
});

describe("describeLocation", () => {
  it.each(LOCATION_CODES)("translates %s in both languages", (code) => {
    expect(en).toHaveProperty(`anonymization.location.${code}`);
    expect(fr).toHaveProperty(`anonymization.location.${code}`);
    expect(describeLocation(code, fr)).not.toBe(describeLocation(code, en));
  });

  it("puts the part number into the sentence", () => {
    expect(describeLocation("slide:7", fr)).toContain("7");
    expect(describeLocation("header:2", fr)).toContain("2");
  });

  it("names a column by the user's own heading", () => {
    expect(describeLocation("column:courriel", fr)).toContain("courriel");
  });

  it("keeps a heading that contains a colon whole", () => {
    expect(describeLocation("column:ville: livraison", fr)).toContain(
      "ville: livraison",
    );
  });

  it("leaves no placeholder behind when a detail is missing", () => {
    expect(describeLocation("slide", fr)).not.toContain("{");
  });

  it("shows an unknown code rather than nothing at all", () => {
    expect(describeLocation("future_part:3", fr)).toBe("future_part:3");
  });
});
