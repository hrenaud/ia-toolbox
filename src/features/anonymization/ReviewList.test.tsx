import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fr } from "../../app/locales/fr";
import type { AnalyzedUnit, Detection } from "../../app/worker/sidecarClient";
import { ReviewList } from "./ReviewList";
import { detectionKey, valueKey } from "./review";

/**
 * This list is the whole point of the two round trips: the user sees what was
 * found and decides. One row per value, the first occurrence in its context,
 * and a type they can correct — a flat list of thirty decisions instead of the
 * fifty repeated questions a ten-line document used to produce. Nothing here
 * may speak in colour alone, and nothing the format cannot rewrite may be
 * offered as a choice — it is still shown, so the user knows it is there.
 */

function detection(fields: Partial<Detection> = {}): Detection {
  return {
    unit_id: "content",
    start: 0,
    end: 11,
    entity_type: "PERSON",
    score: 0.9,
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

const units: AnalyzedUnit[] = [
  { id: "content", location: "document_body", rewritable: true },
  { id: "formulas", location: "sheet_formulas:Ventes", rewritable: false },
  { id: "column-0", location: "column:Nom du contact", rewritable: true },
];

/** Render with selection and type choices owned outside, as the page owns them. */
function Harness({
  detections,
  onChange = () => {},
  onTypeChange = () => {},
}: {
  detections: Detection[];
  onChange?: (next: Set<string>) => void;
  onTypeChange?: (key: string, entityType: string) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [types, setTypes] = useState<Record<string, string>>({});
  return (
    <ReviewList
      detections={detections}
      units={units}
      selected={selected}
      types={types}
      onSelectionChange={(next) => {
        setSelected(next);
        onChange(next);
      }}
      onTypeChange={(key, entityType) => {
        setTypes((prev) => ({ ...prev, [key]: entityType }));
        onTypeChange(key, entityType);
      }}
      t={fr}
    />
  );
}

describe("ReviewList", () => {
  it("says what was found, where it is, and what sits around it", () => {
    render(<Harness detections={[detection()]} />);

    const row = screen.getByRole("checkbox", { name: /Jean Dupont/ });

    expect(row).toHaveAccessibleName(
      expect.stringContaining(fr["anonymization.location.document_body"]),
    );
    expect(
      screen.getByText("…dossier de Jean Dupont est transféré…"),
    ).toBeVisible();
  });

  /**
   * The type is a proposal, not a verdict: two models reading one document
   * disagreed about "Claire Dubois", and the user is the one who knows.
   */
  it("proposes a type the user can correct", async () => {
    const onTypeChange = vi.fn();
    const found = detection();
    render(<Harness detections={[found]} onTypeChange={onTypeChange} />);

    const select = screen.getByRole("combobox", { name: /Jean Dupont/ });
    expect(select).toHaveValue("PERSON");

    await userEvent.selectOptions(select, "ORGANIZATION");

    expect(onTypeChange).toHaveBeenCalledWith(valueKey(found), "ORGANIZATION");
    expect(select).toHaveValue("ORGANIZATION");
  });

  it("shows the type the page already holds for a value", () => {
    const found = detection();
    render(
      <ReviewList
        detections={[found]}
        units={units}
        selected={new Set()}
        types={{ [valueKey(found)]: "LOCATION" }}
        onSelectionChange={() => {}}
        onTypeChange={() => {}}
        t={fr}
      />,
    );

    expect(screen.getByRole("combobox", { name: /Jean Dupont/ })).toHaveValue(
      "LOCATION",
    );
  });

  it("reports one value to the page when it is ticked", async () => {
    const onChange = vi.fn();
    const found = detection();
    render(<Harness detections={[found]} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("checkbox", { name: /Jean Dupont/ }),
    );

    expect(onChange).toHaveBeenCalledWith(new Set([detectionKey(found)]));
  });

  it("asks once about a value found several times", async () => {
    const first = detection({ start: 0, end: 11 });
    const second = detection({ start: 40, end: 51 });
    const onChange = vi.fn();
    render(<Harness detections={[first, second]} onChange={onChange} />);

    const row = screen.getByRole("checkbox", { name: /Jean Dupont/ });
    expect(row).toHaveAccessibleName(expect.stringContaining("2"));

    await userEvent.click(row);

    // One tick, both occurrences: they would get the same pseudonym anyway.
    expect(onChange).toHaveBeenCalledWith(
      new Set([detectionKey(first), detectionKey(second)]),
    );
  });

  it("asks once about a value two models typed differently", () => {
    render(
      <Harness
        detections={[
          detection({ text: "Claire Dubois", start: 0, end: 13 }),
          detection({
            text: "Claire Dubois",
            start: 40,
            end: 53,
            entity_type: "ORGANIZATION",
          }),
        ]}
      />,
    );

    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  });

  /** A word that is always the same word tells the user nothing. */
  it("claims no confidence about a name the model only guessed", () => {
    render(<Harness detections={[detection()]} />);

    expect(screen.queryByText(/Certitude/)).toBeNull();
  });

  it("says how sure it is about a value a pattern decided", () => {
    render(
      <Harness
        detections={[
          detection({
            entity_type: "PHONE_NUMBER",
            text: "06 12 34 56 78",
            score: 0.4,
          }),
        ]}
      />,
    );

    expect(screen.getByText(/Certitude faible/)).toBeVisible();
  });

  it("puts the values the model is least sure of below the rest", () => {
    render(
      <Harness
        detections={[
          detection({ text: "Participants", start: 0, end: 12, likely: false }),
          detection({ text: "Claire Dubois", start: 20, end: 33 }),
        ]}
      />,
    );

    const rows = screen
      .getAllByRole("checkbox")
      .map((box) => box.closest("li")?.textContent ?? "");

    expect(rows.at(-1)).toEqual(expect.stringContaining("Participants"));
    expect(screen.getByText(fr["anonymization.lessLikely"])).toBeVisible();
  });

  it("says nothing about likelihood when every value is a solid one", () => {
    render(<Harness detections={[detection()]} />);

    expect(screen.queryByText(fr["anonymization.lessLikely"])).toBeNull();
  });

  it("shows text the format cannot rewrite, without offering it", () => {
    render(
      <Harness
        detections={[detection({ unit_id: "formulas", text: "Jean Dupont" })]}
      />,
    );

    expect(screen.getByText("Jean Dupont")).toBeInTheDocument();
    expect(screen.getByText(fr["anonymization.notRewritable"])).toBeVisible();
    expect(screen.queryByRole("checkbox", { name: /Jean Dupont/ })).toBeNull();
    // Nor is its type worth correcting: the choice would change nothing.
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("names the place a detection sits in, detail included", () => {
    render(
      <Harness
        detections={[detection({ unit_id: "formulas", text: "Marie" })]}
      />,
    );

    expect(screen.getByText(/Formules de la feuille Ventes/)).toBeVisible();
  });

  /**
   * A column of a table is one decision. Eight names in a column were eight
   * identical questions, and the ninth — the one the model missed — was not
   * asked at all; now the whole column is replaced, so it is covered too.
   */
  describe("a column of a table", () => {
    const cells = [
      cell("Claire Dubois", 0),
      cell("Marc Lefèvre", 14),
      cell("Le Guen", 27),
    ];

    it("asks once, naming the column rather than a value", () => {
      render(<Harness detections={cells} />);

      const [box] = screen.getAllByRole("checkbox");
      expect(screen.getAllByRole("checkbox")).toHaveLength(1);
      expect(box).toHaveAccessibleName(
        expect.stringContaining("Colonne « Nom du contact »"),
      );
    });

    it("shows the values it will replace, including the missed one", () => {
      render(<Harness detections={cells} />);

      expect(
        screen.getByText("Claire Dubois, Marc Lefèvre, Le Guen"),
      ).toBeVisible();
    });

    it("says how many cells the choice covers", () => {
      render(<Harness detections={cells} />);

      expect(screen.getAllByRole("checkbox")[0]).toHaveAccessibleName(
        expect.stringContaining(
          fr["anonymization.columnCells"].replace("{count}", "3"),
        ),
      );
    });

    it("selects every cell of the column with one tick", async () => {
      const onChange = vi.fn();
      render(<Harness detections={cells} onChange={onChange} />);

      await userEvent.click(screen.getAllByRole("checkbox")[0]);

      expect(onChange).toHaveBeenCalledWith(new Set(cells.map(detectionKey)));
    });

    it("retypes the whole column from one menu", async () => {
      const onTypeChange = vi.fn();
      render(<Harness detections={cells} onTypeChange={onTypeChange} />);

      await userEvent.selectOptions(
        screen.getByRole("combobox"),
        "ORGANIZATION",
      );

      expect(onTypeChange).toHaveBeenCalledWith(
        valueKey(cells[0]),
        "ORGANIZATION",
      );
    });

    /** The evidence is the column, not the characters: not ours to score. */
    it("claims no confidence about a column", () => {
      render(
        <Harness
          detections={[cell("a@b.fr", 0), cell("c@d.fr", 10)].map((found) => ({
            ...found,
            entity_type: "EMAIL_ADDRESS",
          }))}
        />,
      );

      expect(screen.queryByText(/Certitude/)).toBeNull();
    });
  });

  it("shows nothing at all when the documents were clean", () => {
    render(<Harness detections={[]} />);

    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});
